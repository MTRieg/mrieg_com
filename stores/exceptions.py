"""
Shared exception definitions for all stores.

Hierarchy:
- StoreError (base for all store exceptions)
  - GameStoreError (game-specific errors)
  - AuthStoreError (auth-specific errors)
"""


# =========================
# Base exception
# =========================

class StoreError(Exception):
    """Base exception for all store-related errors."""
    retryable: bool = True
    

class GameNotFound(StoreError):
    retryable = False


class PlayerNotFound(StoreError):
    retryable = False

class UnexpectedResult(StoreError):
    retryable = True
    #aka, the "how the heck did this happen" exception, such as scenarios that can only occur by breaking ACID

# =========================
# GameStore exceptions
# =========================

class GameStoreError(StoreError):
    """Base exception for game store errors."""
    retryable = True

class GameFull(GameStoreError):
    retryable = False


class PlayerAlreadyExists(GameStoreError):
    retryable = False


class GameAlreadyExists(GameStoreError):
    retryable = False


class PlayerAlreadyJoinedGame(GameStoreError):
    retryable = False


class TurnMismatch(GameStoreError):
    retryable = False


class InvalidState(GameStoreError):
    retryable = False


class CreatorOnlyAction(GameStoreError):
    retryable = False


class SimulationError(GameStoreError):
    retryable = True


# =========================
# AuthStore exceptions
# =========================

class AuthStoreError(StoreError):
    """Base exception for auth store errors."""
    retryable = True


class PasswordNotSet(AuthStoreError):
    retryable = False

class InvalidPassword(AuthStoreError):
    retryable = False


class SessionNotFound(AuthStoreError):
    retryable = False


class SessionExpired(AuthStoreError):
    retryable = False


class PasswordAlreadyExists(AuthStoreError):
    retryable = False
