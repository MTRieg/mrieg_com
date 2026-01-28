import json
from datetime import datetime
from zoneinfo import ZoneInfo
import aiosqlite
from typing import Iterable
import logging

# NOTE: services.game_simulation imports deferred to avoid loading subprocess/Node.js
# dependencies at worker startup time. Imported locally in methods that use it.
from .exceptions import (
    GameNotFound,
    PlayerNotFound,
    GameAlreadyExists,
    PlayerAlreadyExists,
    PasswordAlreadyExists,
    TurnMismatch,
    InvalidState,
    UnexpectedResult
)
from .game_store import GameStore
from .sqlite_auth_store import insert_game_password, insert_player_password
import sqlite3

logger = logging.getLogger(__name__)

class SqliteGameStore(GameStore):

    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db: aiosqlite.Connection = None
        logger.info(f"[STORE] SqliteGameStore initialized with db_path: {db_path}")

    async def init(self):
        """Initialize database connection. Call this after construction."""
        # Use check_same_thread=False to allow multiple workers to access the same DB
        # Use timeout for reasonable concurrent access handling with WAL mode
        # 30s timeout allows queries to wait for write locks to release
        self.db = await aiosqlite.connect(
            self.db_path,
            check_same_thread=False,
            timeout=30.0,
            isolation_level=None  # Disable implicit transactions, manage explicitly
        )
        # Switch to DELETE journal mode instead of WAL to avoid Docker volume locking issues
        # WAL mode has known problems with Docker volume mounts in multi-process scenarios
        await self.db.execute("PRAGMA journal_mode=DELETE")
        await self.db.execute("PRAGMA foreign_keys=ON")
        
        self.db.row_factory = aiosqlite.Row
        logger.info(f"[STORE] Database connection established to {self.db_path}")
        
        # Verify tables exist
        async with self.db.execute("SELECT name FROM sqlite_master WHERE type='table'") as cursor:
            tables = await cursor.fetchall()
            if not tables:
                logger.error(f"[STORE] ✗ No tables found! Database may be empty or corrupted")
                raise RuntimeError(f"Database at {self.db_path} has no tables - initialization may have failed")
            logger.info(f"[STORE] Database has {len(tables)} tables: {[t[0] for t in tables]}")

    async def close(self):
        """Close database connection."""
        if self.db:
            await self.db.close()

    # -------------------------------------------------
    # Lifecycle
    # -------------------------------------------------

    async def create_game(
        self,
        game_id: str,
        *,
        max_players: int = 10,
        board_size: int = 800,
        board_shrink: int = 50,
        turn_interval: int = 24*60*60,
        start_delay: int = 24*60*60,
        game_salt: bytes | None = None,
        game_hashed: bytes | None = None,
    ) -> datetime:
        # Raises: GameAlreadyExists, (and PasswordAlreadyExists if something goes very wrong)
        """Create a new game and initialize state. Returns the scheduled start_time."""
        """Caller must create password separately."""
        logger.info(f"[STORE] Creating game: {game_id}")
        
        await self.db.execute("BEGIN IMMEDIATE")
        # Defer FK checks so we can insert child rows before parent; checked at commit
        await self.db.execute("PRAGMA defer_foreign_keys = ON")
        # Check if game already exists while holding the lock
        cur_check = await self.db.execute(
            "SELECT 1 FROM games WHERE game_id = ?",
            (game_id,),
        )
        exists = await cur_check.fetchone()
        if exists:
            await self.db.rollback()
            raise GameAlreadyExists(f"Game {game_id} already exists")
        # Insert a row into the `games` table so DB triggers that
        # reference `unused_game_ids` (defined in schema.sql) are fired.
        now = datetime.now(ZoneInfo("America/Toronto"))
        start_time = datetime.fromtimestamp(
            now.timestamp() + start_delay,
            tz=ZoneInfo("America/Toronto"),
        )
        
        try:
            # Insert child tables first (game_settings, game_state) before the parent
            # so that AFTER INSERT triggers on `games` find them already present.

            # Create game settings
            await self.db.execute(
                """
                INSERT INTO game_settings (
                    game_id, max_players, board_size, board_shrink, turn_interval
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (game_id, max_players, board_size, board_shrink, turn_interval),
            )

            # Initialize game state
            await self.db.execute(
                """
                INSERT INTO game_state (game_id, turn_number, last_turn_time, next_turn_time)
                VALUES (?, 0, ?, ?)
                """,
                (game_id, now, start_time),
            )

            # Insert core game row (triggers check for settings/state which now exist)
            await self.db.execute(
                "INSERT INTO games (game_id, creator_player_id, start_time, created_at) VALUES (?, ?, ?, ?)",
                (game_id, None, start_time, now),
            )

            # If caller supplied a password, insert it using the auth helper
            if game_salt is not None and game_hashed is not None:
                # Use commit=False so both inserts are part of the same transaction
                # Let PasswordAlreadyExists propagate - it's a different error than GameAlreadyExists
                await insert_game_password(self.db, game_id, game_salt, game_hashed, commit=False)

            await self.db.commit()
            return start_time
        except sqlite3.IntegrityError as exc:
            #should never happen  but just in case
            await self.db.rollback()
            # Unexpected integrity error, likely due to concurrent insert
            raise UnexpectedResult("Unexpected integrity error during game creation") from exc

    async def delete_game(
        self,
        game_id: str,
        owner: str,
    ) -> None:
        # Raises: GameNotFound
        """
        Delete a game and all associated state.
        
        Raises:
            GameNotFound: If the game does not exist.
        """
        await self.db.execute("BEGIN IMMEDIATE")

        # Verify game exists before deleting
        cur = await self.db.execute(
            "SELECT 1 FROM games WHERE game_id = ?",
            (game_id,),
        )
        if await cur.fetchone() is None:
            await self.db.rollback()
            raise GameNotFound(game_id)

        # Delete all related data
        await self.db.execute("DELETE FROM pieces WHERE game_id = ?", (game_id,))
        await self.db.execute(
            "DELETE FROM pieces_old WHERE game_id = ?", (game_id,)
        )
        await self.db.execute(
            "DELETE FROM game_players WHERE game_id = ?", (game_id,)
        )
        await self.db.execute(
            "DELETE FROM game_settings WHERE game_id = ?", (game_id,)
        )
        await self.db.execute(
            "DELETE FROM game_state WHERE game_id = ?", (game_id,)
        )
        # Remove the game row itself so DB state is consistent.
        await self.db.execute(
            "DELETE FROM games WHERE game_id = ?",
            (game_id,),
        )

        await self.db.commit()

    async def start_game(
        self,
        game_id: str,
        pieces: list,
        colors: dict,
        last_turn_time,
    ) -> None:
        # Raises: GameNotFound, TurnMismatch
        """
        Persist initial game state: pieces, player colors, turn number, and last turn time.
        If pieces and colors are not correct, behaviour is undefined.
        
        Raises:
            GameNotFound: If the game does not exist.
            TurnMismatch: If the game has already been started (turn_number != 0).
        """
        await self.db.execute("BEGIN IMMEDIATE")
        
        # Verify game exists
        cur = await self.db.execute(
            "SELECT 1 FROM games WHERE game_id = ?",
            (game_id,),
        )
        if await cur.fetchone() is None:
            await self.db.rollback()
            raise GameNotFound(game_id)
        
        # Verify game hasn't already been started (turn_number should be 0)
        cur = await self.db.execute(
            "SELECT turn_number FROM game_state WHERE game_id = ?",
            (game_id,),
        )
        state_row = await cur.fetchone()
        if state_row and state_row[0] != 0:
            await self.db.rollback()
            raise TurnMismatch(f"Game {game_id} has already been started (turn {state_row[0]})")
        
        # Get turn_interval for calculating next_turn_time
        cur = await self.db.execute(
            "SELECT turn_interval FROM game_settings WHERE game_id = ?",
            (game_id,),
        )
        settings_row = await cur.fetchone()
        turn_interval = settings_row[0] if settings_row else 86400

        # Set player colors
        for player_id, color in colors.items():
            await self.db.execute(
                """
                UPDATE game_players SET color = ? WHERE game_id = ? AND player_id = ?
                """,
                (color, game_id, player_id),
            )

        # Insert pieces
        await self.db.execute(
            "DELETE FROM pieces WHERE game_id = ?",
            (game_id,),
        )
        for p in pieces:
            await self.db.execute(
                """
                INSERT INTO pieces (piece_id, game_id, owner_player_id, x, y, vx, vy, radius, mass)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    p.get("pieceid"),
                    game_id,
                    p.get("owner"),
                    p.get("x"),
                    p.get("y"),
                    p.get("vx"),
                    p.get("vy"),
                    p.get("radius", 30),
                    p.get("mass", 1),
                ),
            )

        # Calculate next_turn_time as last_turn_time + turn_interval seconds
        next_turn_time = datetime.fromtimestamp(
            last_turn_time.timestamp() + turn_interval,
            tz=last_turn_time.tzinfo,
        )

        # Update game state
        await self.db.execute(
            """
            UPDATE game_state SET turn_number = 1, last_turn_time = ?, next_turn_time = ? WHERE game_id = ?
            """,
            (last_turn_time, next_turn_time, game_id),
        )

        await self.db.commit()
        
        # Schedule run_turn task at next_turn_time
        try:
            from workers.tasks import run_turn as celery_run_turn
            celery_run_turn.apply_async(args=[game_id, 1], eta=next_turn_time)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error(f"Failed to schedule run_turn task for {game_id}: {exc}")
    
    async def get_game(self, game_id: str) -> dict:
        # Raises: GameNotFound, InvalidState
        """
        Return all details about a game as a single dictionary.
        Includes settings, state, players, and pieces.
        
        Raises:
            GameNotFound: If the game does not exist.
            InvalidState: If game data is inconsistent across tables.
        """
        # Verify game exists first
        cur = await self.db.execute(
            "SELECT 1 FROM games WHERE game_id = ?",
            (game_id,),
        )
        if await cur.fetchone() is None:
            raise GameNotFound(game_id)
        
        # Get game settings
        cur = await self.db.execute(
            """
            SELECT max_players, board_size, board_shrink, turn_interval
            FROM game_settings
            WHERE game_id = ?
            """,
            (game_id,),
        )
        settings_row = await cur.fetchone()
        if not settings_row:
            raise InvalidState(f"Game {game_id} exists but has no settings")
        settings = {
            "max_players": settings_row[0],
            "board_size": settings_row[1],
            "board_shrink": settings_row[2],
            "turn_interval": settings_row[3],
        }

        # Get game state
        cur = await self.db.execute(
            """
            SELECT turn_number, last_turn_time, next_turn_time
            FROM game_state
            WHERE game_id = ?
            """,
            (game_id,),
        )
        state_row = await cur.fetchone()
        if not state_row:
            raise InvalidState(f"Game {game_id} exists but has no state")
        state = {
            "turn_number": state_row[0],
            "last_turn_time": state_row[1],
            "next_turn_time": state_row[2],
        }

        # Get players
        cur = await self.db.execute(
            """
            SELECT player_id, name, color, submitted_turn
            FROM game_players
            WHERE game_id = ?
            """,
            (game_id,),
        )
        players = {}
        for r in await cur.fetchall():
            players[r[0]] = {
                "name": r[1],
                "color": r[2],
                "submitted_turn": bool(r[3]),
            }

        # Get pieces
        cur = await self.db.execute(
            """
            SELECT piece_id, owner_player_id, x, y, vx, vy, radius, mass
            FROM pieces
            WHERE game_id = ?
            """,
            (game_id,),
        )
        pieces = [
            {
                "piece_id": r[0],
                "owner_player_id": r[1],
                "x": r[2],
                "y": r[3],
                "vx": r[4],
                "vy": r[5],
                "radius": r[6],
                "mass": r[7],
            }
            for r in await cur.fetchall()
        ]

        # Get old pieces
        cur = await self.db.execute(
            """
            SELECT piece_id, owner_player_id, x, y, vx, vy, radius, mass
            FROM pieces_old
            WHERE game_id = ?
            """,
            (game_id,),
        )
        pieces_old = [
            {
                "piece_id": r[0],
                "owner_player_id": r[1],
                "x": r[2],
                "y": r[3],
                "vx": r[4],
                "vy": r[5],
                "radius": r[6],
                "mass": r[7],
            }
            for r in await cur.fetchall()
        ]

        # Get creator
        cur = await self.db.execute(
            "SELECT creator_player_id FROM games WHERE game_id = ?", (game_id,))
        creator_row = await cur.fetchone()
        creator = creator_row[0] if creator_row else None

        return {
            "game_id": game_id,
            "settings": settings,
            "state": state,
            "players": players,
            "pieces": pieces,
            "pieces_old": pieces_old,
            "creator": creator,
        }
    """SQLite-based implementation of GameStore with atomic operations."""


    async def add_unused_game_ids(self, names: Iterable[str]) -> int:
        # Raises: None
        """
        Add multiple suggested game ids to the unused pool.

        Returns number of names actually inserted (skips ids that already
        exist as real games).
        """
        # Normalize and deduplicate
        candidates = {n.strip() for n in names if n and n.strip()}
        if not candidates:
            return 0

        await self.db.execute("BEGIN IMMEDIATE")
        # Exclude any names that already exist as game_id
        placeholders = ",".join("?" for _ in candidates)
        cur = await self.db.execute(
            f"SELECT game_id FROM games WHERE game_id IN ({placeholders})",
            tuple(candidates),
        )
        rows = await cur.fetchall()
        existing = {r[0] for r in rows}
        to_insert = candidates - existing
        if not to_insert:
            await self.db.commit()
            return 0

        now = datetime.now(ZoneInfo("America/Toronto"))
        for nm in to_insert:
            await self.db.execute(
                "INSERT OR IGNORE INTO unused_game_ids (name, last_refreshed) VALUES (?, ?)",
                (nm, now),
            )

        await self.db.commit()
        return len(to_insert)

    async def list_unused_game_ids(self, limit: int = 10) -> list[str]:
        # Raises: None
        """
        Return up to `limit` unused game ids that are not currently leased.
        """
        cur = await self.db.execute(
            "SELECT name FROM unused_game_ids WHERE leased_until IS NULL OR leased_until < datetime('now') ORDER BY last_refreshed DESC LIMIT ?",
            (limit,),
        )
        rows = await cur.fetchall()
        return [r[0] for r in rows]

    async def count_unused_game_ids(self) -> int:
        # Raises: None
        """
        Return count of unused game IDs that are not currently leased.
        """
        cur = await self.db.execute(
            "SELECT COUNT(*) FROM unused_game_ids WHERE leased_until IS NULL OR leased_until < datetime('now')"
        )
        row = await cur.fetchone()
        return row[0] if row else 0

    async def reserve_unused_game_id(self, lease_seconds: int = 120) -> str | None:
        # Raises: None
        """
        Atomically pick one available unused id, set `leased_until` for
        `lease_seconds`, and return the name. Returns `None` if none available.

        Retries briefly if a race is detected.
        """
        for _ in range(3):
            await self.db.execute("BEGIN IMMEDIATE")
            cur = await self.db.execute(
                "SELECT name FROM unused_game_ids WHERE leased_until IS NULL OR leased_until < datetime('now') ORDER BY last_refreshed DESC LIMIT 1"
            )
            row = await cur.fetchone()
            if not row:
                await self.db.rollback()
                return None

            name = row[0]
            # Attempt to claim this name only if it's still unleased.
            cursor = await self.db.execute(
                "UPDATE unused_game_ids SET leased_until = datetime('now', ?) WHERE name = ? AND (leased_until IS NULL OR leased_until < datetime('now'))",
                (f'+{lease_seconds} seconds', name),
            )

            if cursor.rowcount == 1:
                await self.db.commit()
                return name

            await self.db.rollback()

        return None

    async def clear_stale_leases(self) -> int:
        # Raises: None
        """
        Clear all stale leases (where leased_until < now) on unused game IDs.
        Returns the number of rows cleared.
        """
        await self.db.execute("BEGIN IMMEDIATE")
        cursor = await self.db.execute(
            "UPDATE unused_game_ids SET leased_until = NULL WHERE leased_until IS NOT NULL AND leased_until < datetime('now')"
        )
        cleared_count = cursor.rowcount
        await self.db.commit()
        return cleared_count

    async def delete_stale_games(self, inactivity_days: int = 30) -> int:
        # Raises: None
        """
        Delete all games not accessed for more than `inactivity_days` days.
        A game is considered stale if created_at is older than the threshold.
        Returns the number of games deleted (cascade will delete related records).
        """
        await self.db.execute("BEGIN IMMEDIATE")
        cursor = await self.db.execute(
            """
            DELETE FROM games 
            WHERE created_at < datetime('now', ? || ' days')
            """,
            (f"-{inactivity_days}",),
        )
        deleted_count = cursor.rowcount
        await self.db.commit()
        return deleted_count

    async def delete_stale_players(self, inactivity_days: int = 30) -> int:
        # Raises: None
        """
        Delete all players not associated with any active games and older than
        `inactivity_days` days (by date_created). Returns the number of players deleted.
        """
        await self.db.execute("BEGIN IMMEDIATE")
        cursor = await self.db.execute(
            """
            DELETE FROM players 
            WHERE date_created < datetime('now', ? || ' days')
              AND player_id NOT IN (SELECT player_id FROM game_players)
            """,
            (f"-{inactivity_days}",),
        )
        deleted_count = cursor.rowcount
        await self.db.commit()
        return deleted_count

    # -------------------------------------------------
    # Players
    # -------------------------------------------------

    async def create_player(self, player_id: str, *, player_salt: bytes | None = None, player_hashed: bytes | None = None) -> None:
        """Create a global player record.

        If `player_salt` and `player_hashed` are provided, the player's password
        will be inserted in the same DB transaction so creation is atomic.

        Raises:
            PlayerAlreadyExists: If a player with the given ID already exists.
            PasswordAlreadyExists: If password insertion fails (password already set).
        """
        now = datetime.now(ZoneInfo("America/Toronto"))

        await self.db.execute("BEGIN IMMEDIATE")
        # Check if player already exists while holding the lock
        cur = await self.db.execute(
            "SELECT 1 FROM players WHERE player_id = ?",
            (player_id,),
        )
        exists = await cur.fetchone()
        if exists:
            await self.db.rollback()
            raise PlayerAlreadyExists(f"Player {player_id} already exists")

        try:
            await self.db.execute(
                "INSERT INTO players (player_id, date_created) VALUES (?, ?)",
                (player_id, now),
            )

            # If caller provided password bytes, insert password as part of same tx
            if player_salt is not None and player_hashed is not None:
                # Let PasswordAlreadyExists propagate - it's a distinct error
                await insert_player_password(self.db, player_id, player_salt, player_hashed, commit=False)

            await self.db.commit()
        except sqlite3.IntegrityError as exc:
            await self.db.rollback()
            # Unexpected integrity error, likely due to concurrent insert
            raise UnexpectedResult("Unexpected integrity error during player creation") from exc

    async def add_player_to_game(
        self,
        game_id: str,
        player_id: str,
        *,
        name: str,
        color: str = None,
    ) -> None:
        # Raises: GameNotFound, PlayerNotFound, GameFull
        """
        Add a player to a game.
        Enforces max_players invariant.
        
        Raises:
            GameNotFound: If the game does not exist.
            PlayerNotFound: If the player does not exist.
            GameFull: If the game has reached max_players.
        """
        await self.db.execute("BEGIN IMMEDIATE")
        # Check if game exists
        cur = await self.db.execute(
            """
            SELECT max_players FROM game_settings WHERE game_id = ?
            """,
            (game_id,),
        )
        settings = await cur.fetchone()
        if not settings:
            await self.db.rollback()
            raise GameNotFound(game_id)

        # Check if player exists
        cur = await self.db.execute(
            "SELECT 1 FROM players WHERE player_id = ?",
            (player_id,),
        )
        if await cur.fetchone() is None:
            await self.db.rollback()
            raise PlayerNotFound(f"Player {player_id} not found")

        max_players = settings[0]

        cur = await self.db.execute(
            """
            SELECT COUNT(*) as count FROM game_players WHERE game_id = ?
            """,
            (game_id,),
        )
        count_row = await cur.fetchone()
        current_count = count_row[0]

        if current_count >= max_players:
            await self.db.rollback()
            from .game_store import GameFull
            raise GameFull(f"Game {game_id} is full")

        # Add to game
        await self.db.execute(
            """
            INSERT INTO game_players (game_id, player_id, name, color)
            VALUES (?, ?, ?, ?)
            """,
            (game_id, player_id, name, color),
        )

        await self.db.commit()

    async def leave_game(
        self,
        game_id: str,
        player_id: str,
    ) -> None:
        # Raises: GameNotFound, PlayerNotFound
        """
        Remove a player from a game.
        Database triggers will automatically handle creator reassignment.
        """
        await self.db.execute("BEGIN IMMEDIATE")
        # Verify game exists
        cur = await self.db.execute(
            "SELECT game_id FROM games WHERE game_id = ?",
            (game_id,),
        )
        if not await cur.fetchone():
            raise GameNotFound(game_id)

        # Verify player is in the game
        cur = await self.db.execute(
            "SELECT player_id FROM game_players WHERE game_id = ? AND player_id = ?",
            (game_id, player_id),
        )
        if not await cur.fetchone():
            raise PlayerNotFound(f"Player {player_id} not in game {game_id}")

        # Remove player from game (triggers will handle creator reassignment)
        await self.db.execute(
            "DELETE FROM game_players WHERE game_id = ? AND player_id = ?",
            (game_id, player_id),
        )

        await self.db.commit()

    async def list_players(self, game_id: str) -> list[dict]:
        # Raises: None
        """Return players in a game (read-only)."""
        cur = await self.db.execute(
            """
            SELECT player_id, name, color, submitted_turn
            FROM game_players
            WHERE game_id = ?
            """,
            (game_id,),
        )
        rows = await cur.fetchall()
        return [
                {
                    "player_id": r[0],
                    "name": r[1],
                    "color": r[2],
                    "submitted": bool(r[3]),
                }
                for r in rows
            ]

    # -------------------------------------------------
    # Read-side queries (NO state changes)
    # -------------------------------------------------

    async def get_game_summary(self, game_id: str) -> dict:
        # Raises: GameNotFound
        """
        Minimal game state needed by most endpoints.
        """
        cur = await self.db.execute(
            """
            SELECT s.turn_number, s.last_turn_time, s.next_turn_time, st.max_players, st.board_size
            FROM game_state s
            JOIN game_settings st ON s.game_id = st.game_id
            WHERE s.game_id = ?
            """,
            (game_id,),
        )
        row = await cur.fetchone()
        if not row:
            raise GameNotFound(game_id)

        return {
            "game_id": game_id,
            "turn_number": row[0],
            "last_turn_time": row[1],
            "next_turn_time": row[2],
            "max_players": row[3],
            "board_size": row[4],
        }

    async def get_game_settings(self, game_id: str) -> dict:
        # Raises: GameNotFound
        """Return static game configuration."""
        cur = await self.db.execute(
            """
            SELECT max_players, board_size, board_shrink, turn_interval
            FROM game_settings
            WHERE game_id = ?
            """,
            (game_id,),
        )
        row = await cur.fetchone()
        if not row:
            raise GameNotFound(game_id)

        return {
            "max_players": row[0],
            "board_size": row[1],
            "board_shrink": row[2],
            "turn_interval": row[3],
        }

    async def get_game_state(self, game_id: str) -> dict:
        # Raises: GameNotFound
        """
        Return dynamic state:
        - turn_number
        - last_turn_time
        - next_turn_time
        """
        cur = await self.db.execute(
            """
            SELECT turn_number, last_turn_time, next_turn_time
            FROM game_state
            WHERE game_id = ?
            """,
            (game_id,),
        )
        row = await cur.fetchone()
        if not row:
            raise GameNotFound(game_id)

        return {
            "turn_number": row[0],
            "last_turn_time": row[1],
            "next_turn_time": row[2],
        }

    async def get_current_turn(self, game_id: str) -> int:
        # Raises: GameNotFound
        """Return current turn number."""
        cur = await self.db.execute(
            """
            SELECT turn_number FROM game_state WHERE game_id = ?
            """,
            (game_id,),
        )
        row = await cur.fetchone()
        if not row:
            raise GameNotFound(game_id)
        return row[0]
    
    async def get_game_creator(self, game_id: str) -> str | None:
        # Raises: GameNotFound
        """Return the player_id of the game's creator, or None if not set."""
        cur = await self.db.execute(
            "SELECT creator_player_id FROM games WHERE game_id = ?",
            (game_id,),
        )
        row = await cur.fetchone()
        if not row:
            raise GameNotFound(game_id)
        return row[0]

    async def all_players_submitted(self, game_id: str) -> bool:
        # Raises: None
        """
        True if all players have submitted for the current turn.
        """
        cur = await self.db.execute(
            """
             SELECT COUNT(*) as total,
                 SUM(CASE WHEN submitted_turn = 1 THEN 1 ELSE 0 END) as submitted
            FROM game_players
            WHERE game_id = ?
            """,
            (game_id,),
        )
        row = await cur.fetchone()
        if not row or row[0] == 0:
            return False
        return row[0] == row[1]



    # -------------------------------------------------
    # Turn submission (atomic path)
    # -------------------------------------------------

    async def submit_turn(
        self,
        game_id: str,
        player_id: str,
        turn_number: int,
        actions: list[dict],
        owner: str = None,  # Deprecated: no longer used
    ) -> None:
        # Raises: GameNotFound, PlayerNotFound, TurnMismatch
        """
        Full submission flow, atomically:
        - validate game + player
        - validate turn number
        - store submission
        
        Raises:
            GameNotFound: If the game does not exist.
            PlayerNotFound: If the player is not in the game.
            TurnMismatch: If the submission turn does not match current turn.
        """
        await self.db.execute("BEGIN IMMEDIATE")

        try:
            # 1. Verify game exists
            cur = await self.db.execute(
                """
                SELECT turn_number
                FROM game_state
                WHERE game_id = ?
                """,
                (game_id,),
            )
            row = await cur.fetchone()
            if not row:
                raise GameNotFound(game_id)

            # 2. Verify player is in the game
            cur = await self.db.execute(
                "SELECT 1 FROM game_players WHERE game_id = ? AND player_id = ?",
                (game_id, player_id),
            )
            if await cur.fetchone() is None:
                raise PlayerNotFound(f"Player {player_id} not in game {game_id}")

            current_turn = row[0]
            if current_turn != turn_number:
                raise TurnMismatch(
                    f"Expected turn {current_turn}, got {turn_number}"
                )

            # 2. Apply actions by updating piece velocities directly.
            # Also mark the player as having submitted so submission counting works.
            for action in actions:
                piece_id = action.get("pieceid")
                if piece_id is None:
                    continue
                vx = action.get("vx")
                vy = action.get("vy")
                await self.db.execute(
                    """
                    UPDATE pieces
                    SET vx = ?, vy = ?
                    WHERE game_id = ? AND piece_id = ? AND owner_player_id = ?
                    """,
                    (vx, vy, game_id, str(piece_id), player_id),
                )

            # 3. Set submitted marker so submission counting works
            await self.db.execute(
                """
                UPDATE game_players
                SET submitted_turn = 1
                WHERE game_id = ? AND player_id = ?
                """,
                (game_id, player_id),
            )
            
            await self.db.commit()

        except Exception:
            await self.db.rollback()
            raise

    # -------------------------------------------------
    # Turn advancement (atomic path)
    # -------------------------------------------------

    async def advance_turn_if_ready(
        self,
        game_id: str,
        turn_number: int,
    ) -> bool:
        # Raises: GameNotFound, TurnMismatch, InvalidState, SimulationError
        """
        Atomically advance the turn:
        - collect player submissions (if any)
        - snapshot pieces (if applicable)
        - clear submissions
        - increment turn
        - update timestamps

        Returns True if turn was advanced, False otherwise (on exception).
        """
        # Defer import to avoid loading subprocess/Node.js at worker startup
        from services.game_simulation import run_js_simulation, DEFAULT_RADIUS, DEFAULT_MASS
        
        await self.db.execute("BEGIN IMMEDIATE")

        try:
            # 1. Verify game exists + get turn
            cur = await self.db.execute(
                """
                SELECT turn_number
                FROM game_state
                WHERE game_id = ?
                """,
                (game_id,),
            )
            row = await cur.fetchone()
            if not row:
                raise GameNotFound(game_id)

            turn_number_db = row[0]

            if(turn_number_db != turn_number):
                raise TurnMismatch(
                    f"Expected turn {turn_number_db}, got {turn_number}"
                )

            # 2. Collect player submission markers (if any).
            # `submit_turn` writes submitted velocities into the `pieces`
            # table and sets `submitted_turn = 1` for the player. We use
            # the integer marker only to know which players have submitted;
            # we do not re-apply actions here.
            cur = await self.db.execute(
                """
                SELECT player_id, submitted_turn
                FROM game_players
                WHERE game_id = ?
                """,
                (game_id,),
            )
            rows = await cur.fetchall()

            if not rows:
                raise InvalidState("No players in game")

            submitted_player_ids = [r[0] for r in rows if r[1]]

            # 3. Load game settings
            cur = await self.db.execute(
                """
                SELECT max_players, board_size, board_shrink, turn_interval
                FROM game_settings
                WHERE game_id = ?
                """,
                (game_id,),
            )
            settings_row = await cur.fetchone()
            if not settings_row:
                raise InvalidState("Missing game settings")

            game_settings = {
                "max_players": settings_row[0],
                "board_size": settings_row[1],
                "board_shrink": settings_row[2],
                "turn_interval": settings_row[3],
            }

            # 4. Load current pieces
            cur = await self.db.execute(
                """
                SELECT piece_id, owner_player_id, x, y, vx, vy, radius, mass
                FROM pieces
                WHERE game_id = ?
                """,
                (game_id,),
            )
            pieces = [
                {
                    "pieceid": r[0], #yes no underscore, that's what game_simulation.py expects
                    "owner": r[1],
                    "x": r[2],
                    "y": r[3],
                    "vx": r[4],
                    "vy": r[5],
                    "radius": r[6],
                    "mass": r[7],
                }
                for r in await cur.fetchall()
            ]
            
            
            # 5. Run physics simulation
            board_before = int(game_settings.get("board_size", 800))
            board_after = board_before - int(game_settings.get("board_shrink", 50))
            sim_result = run_js_simulation(
                pieces=pieces,
                board_before=board_before,
                board_after=board_after,
            )
            new_pieces = sim_result.get("pieces", [])
            
            print(f"advance_turn_if_ready: sim_result={sim_result}")

            # 6. Snapshot old pieces (optional but safe)
            await self.db.execute(
                "DELETE FROM pieces_old WHERE game_id = ?",
                (game_id,),
            )
            await self.db.execute(
                """
                INSERT INTO pieces_old (piece_id, game_id, owner_player_id, x, y, vx, vy, radius, mass)
                SELECT piece_id, game_id, owner_player_id, x, y, vx, vy, radius, mass
                FROM pieces
                WHERE game_id = ?
                """,
                (game_id,),
            )

            # 7. Replace pieces
            await self.db.execute(
                "DELETE FROM pieces WHERE game_id = ?",
                (game_id,),
            )

            # Preserve owner_player_id from the previous `pieces` by piece_id.
            # Build a map: old_piece_id (string) -> owner_player_id.
            owner_map = {p["pieceid"]: p.get("owner") for p in pieces}

            for p in new_pieces:
                await self.db.execute(
                    """
                    INSERT INTO pieces (
                        piece_id, game_id, owner_player_id,
                        x, y, vx, vy, radius, mass
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        p["pieceid"],
                        game_id,
                        # lookup by piece_id to preserve original owner; fall back
                        # to any owner provided in `new_pieces` if mapping missing.
                        owner_map.get(p.get("pieceid"), p.get("owner")),
                        p["x"],
                        p["y"],
                        p["vx"],
                        p["vy"],
                        p.get("radius", DEFAULT_RADIUS),
                        p.get("mass", DEFAULT_MASS),
                    ),
                )

            # 8. Clear submissions
            await self.db.execute(
                """
                UPDATE game_players
                SET submitted_turn = 0
                WHERE game_id = ?
                """,
                (game_id,),
            )

            # 9. Advance turn and set next_turn_time
            new_last_turn_time = datetime.now(ZoneInfo("America/Toronto"))
            next_turn_time = datetime.fromtimestamp(
                new_last_turn_time.timestamp() + game_settings.get("turn_interval", 86400),
                tz=ZoneInfo("America/Toronto"),
            )
            await self.db.execute(
                """
                UPDATE game_state
                SET turn_number = turn_number + 1,
                    last_turn_time = ?,
                    next_turn_time = ?
                WHERE game_id = ?
                """,
                (new_last_turn_time, next_turn_time, game_id),
            )

            await self.db.commit()
            
            # Schedule run_turn task at next_turn_time for the newly incremented turn
            new_turn_number = turn_number + 1
            try:
                from workers.tasks import run_turn as celery_run_turn
                celery_run_turn.apply_async(args=[game_id, new_turn_number], eta=next_turn_time)
            except Exception as exc:
                import logging
                logging.getLogger(__name__).error(f"Failed to schedule run_turn task for {game_id} turn {new_turn_number}: {exc}")
            
            return True

        except (GameNotFound, TurnMismatch, InvalidState):
            # Known, expected exceptions - let them propagate
            await self.db.rollback()
            raise
        except Exception as e:
            # Unexpected exceptions - log and rollback
            await self.db.rollback()
            logger.error(f"Unexpected error in advance_turn_if_ready for {game_id}: {e}")
            raise UnexpectedResult(f"Unexpected error advancing turn for {game_id}") from e

    # -------------------------------------------------
    # Pieces / simulation data
    # -------------------------------------------------

    async def get_pieces(self, game_id: str) -> list[dict]:
        # Raises: None
        """Return active pieces."""
        cur = await self.db.execute(
            """
            SELECT piece_id, owner_player_id, x, y, vx, vy, radius, mass
            FROM pieces
            WHERE game_id = ?
            """,
            (game_id,),
        )
        rows = await cur.fetchall()
        return [
            {
                "piece_id": r[0],
                "owner_player_id": r[1],
                "x": r[2],
                "y": r[3],
                "vx": r[4],
                "vy": r[5],
                "radius": r[6],
                "mass": r[7],
            }
            for r in rows
        ]

    async def replace_pieces(
        self,
        game_id: str,
        pieces: list[dict],
    ) -> None:
        # Raises: None
        """
        Replace all pieces for a game.
        Used by simulation.
        """
        # Import constants locally to avoid loading subprocess at startup
        from services.game_simulation import DEFAULT_RADIUS, DEFAULT_MASS
        
        await self.db.execute("BEGIN IMMEDIATE")
        await self.db.execute(
            "DELETE FROM pieces WHERE game_id = ?",
            (game_id,),
        )

        for p in pieces:
            await self.db.execute(
                """
                INSERT INTO pieces (
                    piece_id, game_id, owner_player_id,
                    x, y, vx, vy, radius, mass
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    p["piece_id"],
                    game_id,
                    p.get("owner_player_id"),
                    p["x"],
                    p["y"],
                    p["vx"],
                    p["vy"],
                    p.get("radius", DEFAULT_RADIUS),
                    p.get("mass", DEFAULT_MASS),
                ),
            )

        await self.db.commit()



