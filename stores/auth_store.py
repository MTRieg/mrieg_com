from typing import Optional
from abc import ABC, abstractmethod

from .exceptions import (
    AuthStoreError,
    PasswordNotSet,
    InvalidPassword,
    SessionNotFound,
    SessionExpired,
    PasswordAlreadyExists,
)


# =========================
# AuthStore Interface
# =========================

class AuthStore(ABC):
    """
    The AuthStore is the sole authority over authentication and session state.

    Invariants:
    - Passwords are stored as (salt, hashed) tuples
    - Session tokens are unique and time-limited
    - All password verification happens here
    """

    # -------------------------------------------------
    # Password management
    # -------------------------------------------------

    @abstractmethod
    async def set_game_password(
        self,
        game_id: str,
        salt: bytes,
        hashed: bytes,
    ) -> None:
        """Store hashed password for a game."""

    @abstractmethod
    async def set_player_password(
        self,
        player_id: str,
        salt: bytes,
        hashed: bytes,
    ) -> None:
        """Store hashed password for a player."""

    @abstractmethod
    async def get_game_password(
        self,
        game_id: str,
    ) -> Optional[tuple[bytes, bytes]]:
        """
        Retrieve (salt, hashed) for a game.
        Returns None if password not set.
        """

    @abstractmethod
    async def get_player_password(
        self,
        player_id: str,
    ) -> Optional[tuple[bytes, bytes]]:
        """
        Retrieve (salt, hashed) for a player.
        Returns None if password not set.
        """

    # -------------------------------------------------
    # Session management
    # -------------------------------------------------

    @abstractmethod
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
        If a session token already exists, it will be updated.
        
        Raises:
            ValueError: If both game_id and player_id are None.
            GameNotFound: If game_id is provided but game does not exist.
            PlayerNotFound: If player_id is provided but player does not exist.
        """

    @abstractmethod
    async def validate_session_token(
        self,
        session_token: str,
    ) -> Optional[dict]:
        """Validate and return session info if valid.
        
        Returns {game_id, player_id} if token is valid.
        Automatically cleans up expired tokens.
        
        Raises:
            SessionNotFound: If token is not found or has expired.
        """

    @abstractmethod
    async def invalidate_session(
        self,
        session_token: str,
    ) -> None:
        """Explicitly revoke a session (logout).
        
        Raises:
            SessionNotFound: If the session token is not found.
        """

    @abstractmethod
    async def refresh_session(
        self,
        session_token: str,
        new_expires_at,
    ) -> bool:
        """Extend session expiration.
        
        Returns True if refreshed.
        
        Raises:
            SessionNotFound: If session token is not found or has expired.
        """

    @abstractmethod
    async def delete_expired_sessions(self) -> int:
        """Cleanup task. Deletes expired sessions, returns count."""


