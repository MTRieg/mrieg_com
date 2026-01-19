# Abstractions
from .game_store import GameStore
from .auth_store import AuthStore

# Exceptions
from .exceptions import (
    StoreError,
    GameStoreError,
    GameNotFound,
    PlayerNotFound,
    GameFull,
    PlayerAlreadyJoinedGame,
    TurnMismatch,
    InvalidState,
    GameAlreadyExists,
    PlayerAlreadyExists,
    CreatorOnlyAction,
    SimulationError,
    UnexpectedResult,
    AuthStoreError,
    PasswordNotSet,
    InvalidPassword,
    SessionNotFound,
    SessionExpired,
    PasswordAlreadyExists,
)

# Concrete implementations are private; only abstract interfaces are exported.
from .sqlite_game_store import SqliteGameStore as _SqliteGameStore
from .sqlite_auth_store import SqliteAuthStore as _SqliteAuthStore

__all__ = [
    # Abstractions
    "GameStore",
    "AuthStore",
    # Exceptions
    "StoreError",
    "GameStoreError",
    "GameNotFound",
    "PlayerNotFound",
    "GameFull",
    "PlayerAlreadyJoinedGame",
    "TurnMismatch",
    "InvalidState",
    "GameAlreadyExists",
    "PlayerAlreadyExists",
    "CreatorOnlyAction",
    "SimulationError",
    "UnexpectedResult",
    "AuthStoreError",
    "PasswordNotSet",
    "InvalidPassword",
    "SessionNotFound",
    "SessionExpired",
    "PasswordAlreadyExists",
]


# Runtime singletons and initialization helpers
from typing import Optional
import asyncio
import config

# Use abstract interfaces for typing; actual instances are _SqliteGameStore/_SqliteAuthStore
game_store: Optional[GameStore] = None
auth_store: Optional[AuthStore] = None
_stores_initialized = False


def init_stores(db_path: str) -> None:
    """Initialize module-level store singletons for this process.

    This is safe to call multiple times; initialization is idempotent.
    If called inside an existing asyncio event loop it will schedule the
    underlying async connection initialization as a background task; when
    called from synchronous entrypoints (Celery worker process start)
    it will run the async initializers to completion.
    """
    global game_store, auth_store, _stores_initialized

    if _stores_initialized:
        return

    if game_store is None:
        game_store = _SqliteGameStore(db_path)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # no running loop -> safe to run the coroutine
            asyncio.run(game_store.init())
        else:
            # running loop -> schedule initialization
            asyncio.create_task(game_store.init())

    if auth_store is None:
        auth_store = _SqliteAuthStore(db_path)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(auth_store.init())
        else:
            asyncio.create_task(auth_store.init())

    _stores_initialized = True


def get_game_store():
    """Get game store, initializing if needed (for lazy initialization in Celery workers)."""
    global game_store
    if game_store is None:
        init_stores(config.DB_PATH)
    if game_store is None:
        raise RuntimeError("Failed to initialize game store")
    return game_store


def get_auth_store():
    """Get auth store, initializing if needed (for lazy initialization in Celery workers)."""
    global auth_store
    if auth_store is None:
        init_stores(config.DB_PATH)
    if auth_store is None:
        raise RuntimeError("Failed to initialize auth store")
    return auth_store

