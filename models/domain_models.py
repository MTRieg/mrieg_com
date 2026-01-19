"""Domain-level typed models used by services and stores.

Prefer `TypedDict` for lightweight structural typing that maps directly to
the JSON-like dicts stored in the database. These are minimal and can be
extended as the domain grows.
"""
from __future__ import annotations

from typing import TypedDict, Any
from datetime import datetime


class Piece(TypedDict, total=False):
	owner: str
	pieceid: int
	x: float
	y: float
	vx: float
	vy: float
	color: str | None
	status: str | None


class Player(TypedDict, total=False):
	name: str
	submitted_turn: bool | None
	color: str | None


class GameSettings(TypedDict, total=False):
	max_players: int
	board_size: int
	board_shrink: int
	turn_interval: int


class GameState(TypedDict, total=False):
	turn_number: int
	last_turn_time: datetime | None
	pieces: list[Piece]


class Game(TypedDict, total=False):
	id: str
	creator: str | None
	settings: GameSettings
	players: dict[str, Player]
	state: GameState
	start_time: datetime | None


__all__ = ["Piece", "Player", "GameSettings", "GameState", "Game"]
