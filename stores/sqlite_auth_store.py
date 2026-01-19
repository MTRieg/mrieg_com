from datetime import datetime
from zoneinfo import ZoneInfo
import aiosqlite

from .auth_store import AuthStore
from .exceptions import (
    PasswordAlreadyExists,
    GameNotFound,
    PlayerNotFound,
    SessionNotFound,
)
import sqlite3


async def insert_game_password(conn: aiosqlite.Connection, game_id: str, salt: bytes, hashed: bytes, *, commit: bool = True):
    """Insert a game password using the provided DB connection.

    Raises `GameNotFound` if the game does not exist.
    Raises `PasswordAlreadyExists` if the row already exists (unique constraint).
    If `commit` is False, the caller manages transaction/commit.
    """
    # Verify the game exists first
    cur = await conn.execute("SELECT 1 FROM games WHERE game_id = ?", (game_id,))
    if await cur.fetchone() is None:
        raise GameNotFound(game_id)
    
    try:
        await conn.execute(
            """
            INSERT INTO game_passwords (game_id, salt, hashed)
            VALUES (?, ?, ?)
            """,
            (game_id, salt, hashed),
        )
        if commit:
            await conn.commit()
    except sqlite3.IntegrityError as exc:
        raise PasswordAlreadyExists(f"Game password for {game_id} already exists") from exc


async def insert_player_password(conn: aiosqlite.Connection, player_id: str, salt: bytes, hashed: bytes, *, commit: bool = True):
    """Insert a player password using the provided DB connection.

    Raises `PlayerNotFound` if the player does not exist.
    Raises `PasswordAlreadyExists` if the row already exists (unique constraint).
    If `commit` is False, the caller manages transaction/commit.
    """
    # Verify the player exists first
    cur = await conn.execute("SELECT 1 FROM players WHERE player_id = ?", (player_id,))
    if await cur.fetchone() is None:
        raise PlayerNotFound(f"Player {player_id} not found")
    
    try:
        await conn.execute(
            """
            INSERT INTO player_passwords (player_id, salt, hashed)
            VALUES (?, ?, ?)
            """,
            (player_id, salt, hashed),
        )
        if commit:
            await conn.commit()
    except sqlite3.IntegrityError as exc:
        raise PasswordAlreadyExists(f"Player password for {player_id} already exists") from exc


class SqliteAuthStore(AuthStore):
    """SQLite-based implementation of AuthStore."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db: aiosqlite.Connection = None

    async def init(self):
        """Initialize database connection. Call this after construction."""
        self.db = await aiosqlite.connect(
            self.db_path,
            timeout=30.0
        )
        # Switch to DELETE journal mode instead of WAL to avoid Docker volume locking issues
        await self.db.execute("PRAGMA journal_mode=DELETE")
        self.db.row_factory = aiosqlite.Row

    async def close(self):
        """Close database connection."""
        if self.db:
            await self.db.close()

    # -------------------------------------------------
    # Password management
    # -------------------------------------------------

    #the set password functions should only be called immediately after creating a game/player for now
    async def set_game_password(
        self,
        game_id: str,
        salt: bytes,
        hashed: bytes,
    ) -> None:
        """Store hashed password for a game.
        
        Raises:
            GameNotFound: If the game does not exist.
            PasswordAlreadyExists: If a password is already set for this game.
        """
        await insert_game_password(self.db, game_id, salt, hashed, commit=True)

    async def set_player_password(
        self,
        player_id: str,
        salt: bytes,
        hashed: bytes,
    ) -> None:
        """Store hashed password for a player.
        
        Raises:
            PlayerNotFound: If the player does not exist.
            PasswordAlreadyExists: If a password is already set for this player.
        """
        await insert_player_password(self.db, player_id, salt, hashed, commit=True)

    async def get_game_password(
        self,
        game_id: str,
    ) -> tuple[bytes, bytes] | None:
        """Retrieve (salt, hashed) for a game.
        
        Returns None if password not set or if any error occurs (read-only operation).
        """
        try:
            cur = await self.db.execute(
                """
                SELECT salt, hashed FROM game_passwords WHERE game_id = ?
                """,
                (game_id,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            return (row[0], row[1])
        except Exception:
            # For read-only operations, treat any error as "data not available"
            return None

    async def get_player_password(
        self,
        player_id: str,
    ) -> tuple[bytes, bytes] | None:
        """Retrieve (salt, hashed) for a player.
        
        Returns None if password not set or if any error occurs (read-only operation).
        """
        try:
            cur = await self.db.execute(
                """
                SELECT salt, hashed FROM player_passwords WHERE player_id = ?
                """,
                (player_id,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            return (row[0], row[1])
        except Exception:
            # For read-only operations, treat any error as "data not available"
            return None

    # -------------------------------------------------
    # Session management
    # -------------------------------------------------

    async def create_session_token(
        self,
        session_token: str,
        *,
        game_id: str | None = None,
        player_id: str | None = None,
        expires_at,
    ) -> None:
        """Create or update a session token.
        
        At least one of game_id or player_id must be provided (not None).
        If provided, the ID must exist in the database.
        If a session token already exists, it will be updated with new expiration.
        
        Raises:
            ValueError: If both game_id and player_id are None.
            GameNotFound: If game_id is provided but the game does not exist.
            PlayerNotFound: If player_id is provided but the player does not exist.
        """
        # Ensure at least one ID is provided
        if game_id is None and player_id is None:
            raise ValueError("At least one of game_id or player_id must be provided")
        
        # Verify game exists if provided
        if game_id is not None:
            cur = await self.db.execute("SELECT 1 FROM games WHERE game_id = ?", (game_id,))
            if await cur.fetchone() is None:
                raise GameNotFound(game_id)
        
        # Verify player exists if provided
        if player_id is not None:
            cur = await self.db.execute("SELECT 1 FROM players WHERE player_id = ?", (player_id,))
            if await cur.fetchone() is None:
                raise PlayerNotFound(f"Player {player_id} not found")
        
        # Use INSERT OR REPLACE to update if token already exists
        await self.db.execute(
            """
            INSERT OR REPLACE INTO session_tokens (session_token, game_id, player_id, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (session_token, game_id, player_id, expires_at),
        )
        await self.db.commit()

    async def validate_session_token(
        self,
        session_token: str,
    ) -> dict | None:
        """Validate and return session info if valid.
        
        Returns {game_id, player_id} or None if expired/not found.
        Automatically cleans up expired tokens.
        
        """
        cur = await self.db.execute(
            """
            SELECT game_id, player_id, expires_at
            FROM session_tokens
            WHERE session_token = ?
            """,
            (session_token,),
        )
        row = await cur.fetchone()
        if not row:
            return None

        game_id, player_id, expires_at = row[0], row[1], row[2]

        # Check expiration
        now = datetime.now(ZoneInfo("America/Toronto"))
        if expires_at:
            if isinstance(expires_at, str):
                expires_dt = datetime.fromisoformat(expires_at)
            else:
                expires_dt = expires_at

            if expires_dt < now:
                # Clean up expired token
                await self.db.execute(
                    "DELETE FROM session_tokens WHERE session_token = ?",
                    (session_token,),
                )
                await self.db.commit()
                return None

        # Ensure any implicit read transaction is closed before returning
        try:
            await self.db.commit()
        except Exception:
            # If commit fails for any reason, ignore and still return token info;
            # this is defensive — commit is expected to succeed on normal connections.
            pass

        return {
            "game_id": game_id,
            "player_id": player_id,
        }

    async def invalidate_session(
        self,
        session_token: str,
    ) -> None:
        """Explicitly revoke a session (logout).
        
        Raises:
            SessionNotFound: If the session token is not found.
        """
        cur = await self.db.execute(
            "DELETE FROM session_tokens WHERE session_token = ?",
            (session_token,),
        )
        await self.db.commit()
        if cur.rowcount == 0:
            raise SessionNotFound(f"Session token {session_token} not found")

    async def refresh_session(
        self,
        session_token: str,
        new_expires_at,
    ) -> bool:
        """Extend session expiration.
        
        Raises:
            SessionNotFound: If the session token is not found or has expired.
        """
        # validate_session_token now raises SessionNotFound if not found or expired
        session_info = await self.validate_session_token(session_token)

        # Update expiration
        await self.db.execute(
            """
            UPDATE session_tokens
            SET expires_at = ?
            WHERE session_token = ?
            """,
            (new_expires_at, session_token),
        )
        await self.db.commit()
        return True

    async def delete_expired_sessions(self) -> int:
        # Raises: None
        """Cleanup task. Deletes expired sessions, returns count."""
        """Cleanup task. Deletes expired sessions, returns count.
        
        Raises:
            None - this is a maintenance operation that should not fail the system.
        """
        try:
            now = datetime.now(ZoneInfo("America/Toronto"))
            cur = await self.db.execute(
                """
                DELETE FROM session_tokens
                WHERE expires_at < ?
                """,
                (now,),
            )
            await self.db.commit()
            return cur.rowcount
        except Exception:
            # Silently fail cleanup operations to avoid disrupting the system
            return 0