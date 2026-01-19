from urllib import request
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import secrets
import logging

from stores import (
	get_game_store, 
	get_auth_store, 
	GameNotFound,
	GameFull,
	PlayerNotFound,
	PlayerAlreadyExists,
	PasswordAlreadyExists,
)
from models import BaseModelPlus
from utils.cookies import check_credentials
from .auth import _hash_password, _append_cookie
from utils.validation import is_valid_name

logger = logging.getLogger(__name__)

router = APIRouter()


class CreatePlayerRequest(BaseModel):
	player_id: str
	password: str


class CreatePlayerAndJoinGameRequest(CreatePlayerRequest):
	game_id: str


@router.post("/api/create_player")
async def create_player(req: CreatePlayerRequest, game_store = Depends(get_game_store), auth_store = Depends(get_auth_store)):

	if(not is_valid_name(req.player_id)):
		raise HTTPException(status_code=400, detail="Invalid player ID format. (Use only letters, numbers, spaces, and .'-`’· characters.)")

	"""Create a new player and return session cookie."""
	# Hash password first so we can pass it into the store for atomic creation
	player_salt, player_hashed = _hash_password(req.password)
	try:
		await game_store.create_player(req.player_id, player_salt=player_salt, player_hashed=player_hashed)
	except PlayerAlreadyExists:
		logger.warning(f"Attempt to create player with existing ID: {req.player_id}")
		return JSONResponse({"error": "Player ID already exists"}, status_code=400)
	except PasswordAlreadyExists:
		logger.warning(f"Attempt to create player with existing password: {req.player_id}")
		return JSONResponse({"error": "Player password already registered"}, status_code=400)
	except Exception as e:
		logger.error(f"Failed to create player: {e}", exc_info=True)
		return JSONResponse({"error": str(e)}, status_code=500)

	# Create session token
	try:
		session_token = secrets.token_urlsafe(32)
		expires_at = datetime.now(ZoneInfo("America/Toronto")) + timedelta(days=2)
		await auth_store.create_session_token(
			session_token,
			game_id=None,
			player_id=req.player_id,
			expires_at=expires_at,
		)
	except Exception as e:
		logger.error(f"Failed to create session token for player: {e}", exc_info=True)
		raise HTTPException(status_code=500, detail="Failed to create session token")

	output = JSONResponse({"player_id": req.player_id})
	return _append_cookie(output, f"player:{req.player_id}", session_token)


@router.post("/api/register_for_game")
async def register_for_game(request: Request, req: CreatePlayerAndJoinGameRequest, game_store = Depends(get_game_store), auth_store = Depends(get_auth_store)):
	# call check credentials first on the gameid
	creds = await check_credentials(request, game_id=req.game_id, auth_store=auth_store)
	game_id = creds["game_id"]
	#if game_id does not exist, return 401
	if not game_id:
		raise HTTPException(status_code=401, detail="Invalid or unauthenticated game ID")

	"""Create a new player and join an existing game."""
	# Hash password first so we can pass it into the store for atomic creation
	salt, hashed = _hash_password(req.password)
	try:
		await game_store.create_player(req.player_id, player_salt=salt, player_hashed=hashed)
	except PlayerAlreadyExists:
		logger.warning(f"Attempt to register player with existing ID: {req.player_id}")
		return JSONResponse({"error": "Player ID already exists"}, status_code=400)
	except PasswordAlreadyExists:
		logger.warning(f"Attempt to register player with existing password: {req.player_id}")
		return JSONResponse({"error": "Player password already registered"}, status_code=400)
	except Exception as e:
		logger.error(f"Failed to create player: {e}", exc_info=True)
		return JSONResponse({"error": str(e)}, status_code=500)
	
	# Try to join game
	try:
		await game_store.add_player_to_game(
			game_id,
			req.player_id,
			name=req.player_id,
			color=None,
		)
	except GameNotFound:
		logger.warning(f"Attempt to join non-existent game: {game_id}")
		return JSONResponse({"error": "Game not found"}, status_code=404)
	except PlayerNotFound:
		logger.warning(f"Attempt to add non-existent player to game: {req.player_id}")
		return JSONResponse({"error": "Player not found"}, status_code=404)
	except GameFull:
		logger.info(f"Attempt to join full game: {game_id}")
		return JSONResponse({"error": "Game is full"}, status_code=400)
	except Exception as e:
		logger.error(f"Failed to add player to game: {e}", exc_info=True)
		return JSONResponse({"error": str(e)}, status_code=500)
		
	
	# Create session token
	try:
		session_token = secrets.token_urlsafe(32)
		expires_at = datetime.now(ZoneInfo("America/Toronto")) + timedelta(days=2)
		await auth_store.create_session_token(
			session_token,
			game_id=game_id,
			player_id=req.player_id,
			expires_at=expires_at,
		)
	except Exception as e:
		logger.error(f"Failed to create session token: {e}", exc_info=True)
		raise HTTPException(status_code=500, detail="Failed to create session token")
	
	output = JSONResponse({
		"message": "Player created and joined game successfully",
		"player_id": req.player_id,
		"game_id": game_id,
	})
	output = _append_cookie(output, f"player:{req.player_id}", session_token)
	output = _append_cookie(output, f"game:{game_id}", session_token)
	return output
