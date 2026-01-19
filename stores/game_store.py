from typing import Optional, Iterable
from datetime import datetime
from abc import ABC, abstractmethod

from .exceptions import (
    GameStoreError,
    GameNotFound,
    PlayerNotFound,
    GameFull,
    PlayerAlreadyExists,
    TurnMismatch,
    InvalidState,
    GameAlreadyExists,
)


# =========================
# GameStore Interface
# =========================

class GameStore(ABC):

    @abstractmethod
    async def start_game(
        self,
        game_id: str,
        pieces: list,
        colors: dict,
        last_turn_time,
    ) -> None:
        """Persist initial game state: pieces, player colors, turn number, and last turn time.
        
        Raises:
            GameNotFound: If the game does not exist.
        """

        
    """
    The GameStore is the sole authority over game state.

    Invariants:
    - Turn advancement is atomic
    - A player submits at most once per turn
    - A game cannot be advanced or deleted while locked
    - All concurrency control lives here
    """

    # -------------------------------------------------
    # Lifecycle
    # -------------------------------------------------

    @abstractmethod
    async def create_game(
        self,
        game_id: str,
        *,
        max_players: int,
        board_size: int,
        board_shrink: int,
        turn_interval: int,
        game_salt: bytes | None = None,
        game_hashed: bytes | None = None,
        start_delay: int = 86400,
    ) -> datetime:
        """Create a new game and initialize state.

        Implementations should also insert a row into the `games` table
        (for example: `INSERT INTO games (game_id, creator_player_id, start_time) ...`)
        so that DB triggers and the `unused_game_ids` pool remain consistent.
        """


    @abstractmethod
    async def delete_game(
        self,
        game_id: str,
        owner: str,
    ) -> None:
        """Delete a game and all associated state.
        
        Raises:
            GameNotFound: If the game does not exist.
        """


    # -------------------------------------------------
    # Players
    # -------------------------------------------------

    @abstractmethod
    async def create_player(self, player_id: str, *, player_salt: bytes | None = None, player_hashed: bytes | None = None) -> None:
        """Create a global player record.
        
        Raises:
            PlayerAlreadyExists: If a player with this ID already exists.
            PasswordAlreadyExists: If password insertion fails (password already set).
        """


    @abstractmethod
    async def add_player_to_game(
        self,
        game_id: str,
        player_id: str,
        *,
        name: str,
        color: Optional[str],
    ) -> None:
        """Add a player to a game.
        
        Enforces max_players invariant.
        
        Raises:
            GameNotFound: If the game does not exist.
            PlayerNotFound: If the player does not exist.
            GameFull: If the game has reached max_players.
        """


    @abstractmethod
    async def leave_game(
        self,
        game_id: str,
        player_id: str,
    ) -> None:
        """
        Remove a player from a game.
        Database triggers will handle creator reassignment.
        """


    @abstractmethod
    async def list_players(
        self,
        game_id: str,
    ) -> list[dict]:
        """Return players in a game (read-only)."""


    # -------------------------------------------------
    # Read-side queries (NO state changes)
    # -------------------------------------------------

    @abstractmethod
    async def get_game(self, game_id: str) -> dict:
        """Return all details about a game as a single dictionary.
        
        Should include settings, state, players, pieces, and creator.
        
        Raises:
            GameNotFound: If the game does not exist.
            InvalidState: If game data is inconsistent across tables.
        """

    @abstractmethod
    async def get_game_summary(self, game_id: str) -> dict:
        """
        Minimal game state needed by most endpoints.
        """


    @abstractmethod
    async def get_game_settings(self, game_id: str) -> dict:
        """Return static game configuration."""


    @abstractmethod
    async def get_game_state(self, game_id: str) -> dict:
        """
        Return dynamic state:
        - turn_number
        - last_turn_time
        """


    @abstractmethod
    async def get_current_turn(self, game_id: str) -> int:
        """Return current turn number."""

    async def get_game_creator(self, game_id: str) -> str | None:
        """Return the player ID of the game's creator, or none if not found."""


    @abstractmethod
    async def all_players_submitted(self, game_id: str) -> bool:
        """
        True if all players have submitted for the current turn.
        """



    # -------------------------------------------------
    # Turn submission (atomic path)
    # -------------------------------------------------

    @abstractmethod
    async def submit_turn(
        self,
        game_id: str,
        player_id: str,
        turn_number: int,
        actions: list[dict],
        owner: str,
    ) -> None:
        """Atomically persist a player's turn actions (piece velocities).

        Raises:
            GameNotFound: If game doesn't exist.
            PlayerNotFound: If player is not in the game.
            TurnMismatch: If current turn doesn't match turn_number.
        """


    # -------------------------------------------------
    # Turn advancement (atomic path)
    # -------------------------------------------------

    @abstractmethod
    async def advance_turn_if_ready(
        self,
        game_id: str,
        turn_number: int
    ) -> bool:
        """Atomically advance the turn if ready.
        
        - Run physics simulation on current pieces
        - Persist new piece state
        - Increment turn
        - Update turn timestamps

        Returns True if advanced.
        
        Raises:
            GameNotFound: If the game does not exist.
            TurnMismatch: If provided turn number does not match current turn.
            InvalidState: If game data is inconsistent.
            UnexpectedResult: If an unexpected error occurs.
        """


    # -------------------------------------------------
    # Pieces / simulation data
    # -------------------------------------------------

    @abstractmethod
    async def get_pieces(self, game_id: str) -> list[dict]:
        """Return active pieces."""


    @abstractmethod
    async def replace_pieces(
        self,
        game_id: str,
        pieces: Iterable[dict],
    ) -> None:
        """
        Replace all pieces for a game.
        Used by simulation.

        """
    
    
    # -------------------------------------------------
    # Unused game id suggestions
    # -------------------------------------------------

    @abstractmethod
    async def add_unused_game_ids(self, names: Iterable[str]) -> int:
        """
        Add multiple suggested game ids to the unused pool.

        Returns the number of names actually inserted (existing ids are skipped).
        """

    @abstractmethod
    async def list_unused_game_ids(self, limit: int = 10) -> list[str]:
        """
        Return up to `limit` candidate unused game ids that are not currently leased.
        """

    @abstractmethod
    async def count_unused_game_ids(self) -> int:
        """
        Return count of unused game IDs that are not currently leased.
        """

    @abstractmethod
    async def reserve_unused_game_id(self, lease_seconds: int = 120) -> Optional[str]:
        """
        Atomically reserve (lease) one unused game id for `lease_seconds` and
        return the name, or `None` if none available.
        """

    @abstractmethod
    async def clear_stale_leases(self) -> int:
        """
        Clear all stale leases (where leased_until < now) on unused game IDs.
        Returns the number of rows cleared.
        """

    @abstractmethod
    async def delete_stale_games(self, inactivity_days: int = 30) -> int:
        """
        Delete all games not accessed (created_at or last_turn_time) for more than
        `inactivity_days` days. Returns the number of games deleted.
        """

    @abstractmethod
    async def delete_stale_players(self, inactivity_days: int = 30) -> int:
        """
        Delete all players not associated with any active games and older than
        `inactivity_days` days (by date_created). Returns the number of players deleted.
        """



