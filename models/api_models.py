"""Pydantic request/response models for the FastAPI endpoints.

These models are intentionally small and can be expanded as endpoints are
implemented. Keep transport concerns (validation, docs) here and keep
business/domain types in `models.domain_models`.
"""
from __future__ import annotations

from pydantic import BaseModel
from typing import Any
from datetime import datetime


class GameSettings(BaseModel):
	max_players: int = 4
	board_size: int = 800
	board_shrink: int = 50
	turn_interval: int = 86400  # seconds


class CreateGameRequest(BaseModel):
	game_id: str
	password: str
	start_delay: int = 86400  # seconds
	settings: GameSettings | None = None


class CreatePlayerRequest(BaseModel):
	player_id: str
	password: str


class CreatePlayerAndJoinGameRequest(CreatePlayerRequest):
	game_id: str


class SubmitTurnRequest(BaseModel):
	player_id: str | None = None
	game_id: str | None = None
	turn_number: int
	actions: list[dict[str, Any]]


class ApplyMovesAndRunGameRequest(BaseModel):
	game_id: str
	turn_number: int


# --- Common base models from legacy routes ---
class BaseModelPlus(BaseModel):
	player_id: str | None = None
	game_id: str | None = None


class BaseModelPlusWithPassword(BaseModelPlus):
	game_password: str | None = None
	player_password: str | None = None


class VerifiedBaseModelPlus(BaseModelPlus):
	last_player: str | None = None
	last_game: str | None = None


class GameStateResponse(BaseModel):
	creator: str | None = None
	turn_number: int
	last_turn_time: datetime | None = None
	board_size: int
	board_shrink: int
	players: dict[str, Any]
	pieces: list[dict[str, Any]]
	next_turn_deadline: datetime | None = None


__all__ = [
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
]
