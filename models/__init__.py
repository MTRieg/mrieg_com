"""Data models used by the application.

Split into:
- `api_models`: Pydantic models used for request/response validation
- `domain_models`: internal domain objects or typed dicts used in business logic

Import submodules to make them available as `models.api_models`.
"""

from . import api_models, domain_models

# Re-export selected API models (Pydantic models used for request/response)
from .api_models import (
	GameSettings,
	CreateGameRequest,
	CreatePlayerRequest,
	CreatePlayerAndJoinGameRequest,
	SubmitTurnRequest,
	ApplyMovesAndRunGameRequest,
	BaseModelPlus,
	BaseModelPlusWithPassword,
	VerifiedBaseModelPlus,
	GameStateResponse,
)

# Re-export domain models (TypedDicts). Alias `GameSettings` from the domain
# module to avoid a name collision with the Pydantic `GameSettings`.
from .domain_models import (
	Piece,
	Player,
	GameState,
	Game,
	GameSettings as DomainGameSettings,
)

__all__ = [
	# submodules
	"api_models",
	"domain_models",
	# api models
	"GameSettings",
	"CreateGameRequest",
	"CreatePlayerRequest",
	"CreatePlayerAndJoinGameRequest",
	"SubmitTurnRequest",
	"ApplyMovesAndRunGameRequest",
	"BaseModelPlus",
	"BaseModelPlusWithPassword",
	"VerifiedBaseModelPlus",
	"GameStateResponse",
	# domain models
	"Piece",
	"Player",
	"GameState",
	"Game",
	"DomainGameSettings",
]
