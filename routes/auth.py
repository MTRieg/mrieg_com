from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import secrets
import bcrypt
import logging

from stores import get_auth_store, GameNotFound, PlayerNotFound, SessionNotFound

logger = logging.getLogger(__name__)

router = APIRouter()


class AuthRequest(BaseModel):
	game_id: Optional[str] = None
	game_password: Optional[str] = None
	player_id: Optional[str] = None
	player_password: Optional[str] = None


def _hash_password(password: str) -> tuple[bytes, bytes]:
	"""Hash a password using bcrypt and return (salt, hashed)."""
	# bcrypt.gensalt() generates a salt with default cost factor of 12
	# bcrypt.hashpw() handles both salt generation and hashing
	salt = bcrypt.gensalt(rounds=12)
	hashed = bcrypt.hashpw(password.encode(), salt)
	# bcrypt stores salt within hashed, but return both for consistency
	return salt, hashed


def _verify_password(password: str, salt: bytes, hashed: bytes) -> bool:
	"""Verify a password against bcrypt hash."""
	# bcrypt.checkpw compares plaintext against the hashed value
	# Note: salt is embedded in hashed, but we pass it for interface consistency
	try:
		return bcrypt.checkpw(password.encode(), hashed)
	except Exception:
		return False


def _append_cookie(response: JSONResponse, key: str, value: str, expires: int = 2 * 24 * 60 * 60):
	"""Attach a cookie to the response."""
	response.set_cookie(key=key, value=value, httponly=False, expires=expires)
	return response


async def create_session_and_append_cookies(response: JSONResponse, auth_store, *, game_id: str | None = None, player_id: str | None = None, expires_days: int = 2) -> JSONResponse:
	"""Create a session token in the auth store and append appropriate cookies to `response`.

	Returns the modified response.
	
	Raises:
		GameNotFound: if game_id is provided but game does not exist
		PlayerNotFound: if player_id is provided but player does not exist
		ValueError: if both game_id and player_id are None
		HTTPException: if token creation fails (500)
	"""
	session_token = secrets.token_urlsafe(32)
	expires_at = datetime.now(ZoneInfo("America/Toronto")) + timedelta(days=expires_days)
	try:
		await auth_store.create_session_token(
			session_token,
			game_id=game_id,
			player_id=player_id,
			expires_at=expires_at,
		)
	except (GameNotFound, PlayerNotFound, ValueError) as e:
		# These are expected validation errors - propagate to caller to handle
		raise
	except Exception as e:
		# Unexpected errors - log and return 500
		logger.error(f"Failed to create session token: {e}", exc_info=True)
		raise HTTPException(status_code=500, detail="Failed to create session token")

	if game_id:
		response = _append_cookie(response, f"game:{game_id}", session_token)
		response = _append_cookie(response, "last_game", session_token)
	if player_id:
		response = _append_cookie(response, f"player:{player_id}", session_token)
		response = _append_cookie(response, "last_player", session_token)

	return response


@router.post("/api/create_session_cookie")
async def request_token(req: AuthRequest, auth_store = Depends(get_auth_store)):
	"""Request a session token for a game and/or player."""
	# Validate game password if provided
	if req.game_id and req.game_password:
		salt_hash = await auth_store.get_game_password(req.game_id)
		if not salt_hash:
			return JSONResponse({"error": "Invalid game credentials"}, status_code=403)
		salt, hashed = salt_hash
		if not _verify_password(req.game_password, salt, hashed):
			return JSONResponse({"error": "Invalid game credentials"}, status_code=403)
	
	# Validate player password if provided
	if req.player_id and req.player_password:
		salt_hash = await auth_store.get_player_password(req.player_id)
		if not salt_hash:
			return JSONResponse({"error": "Invalid player credentials"}, status_code=403)
		salt, hashed = salt_hash
		if not _verify_password(req.player_password, salt, hashed):
			return JSONResponse({"error": "Invalid player credentials"}, status_code=403)
	
	# Create session token
	try:
		session_token = secrets.token_urlsafe(32)
		expires_at = datetime.now(ZoneInfo("America/Toronto")) + timedelta(days=2)
		await auth_store.create_session_token(
			session_token,
			game_id=req.game_id,
			player_id=req.player_id,
			expires_at=expires_at,
		)
	except GameNotFound:
		logger.warning(f"Attempt to create token for non-existent game: {req.game_id}")
		raise HTTPException(status_code=404, detail="Game not found")
	except PlayerNotFound:
		logger.warning(f"Attempt to create token for non-existent player: {req.player_id}")
		raise HTTPException(status_code=404, detail="Player not found")
	except ValueError as e:
		logger.warning(f"Invalid token creation request: {e}")
		raise HTTPException(status_code=400, detail="Both game_id and player_id cannot be None")
	except Exception as e:
		logger.error(f"Failed to create session token: {e}", exc_info=True)
		raise HTTPException(status_code=500, detail="Failed to create session token")
	
	output = JSONResponse({"message": "Session token created"})
	if req.game_id:
		output = _append_cookie(output, f"game:{req.game_id}", session_token)
		output = _append_cookie(output, "last_game", session_token)
	if req.player_id:
		output = _append_cookie(output, f"player:{req.player_id}", session_token)
		output = _append_cookie(output, "last_player", session_token)
	return output


@router.post("/api/revoke_token")
async def revoke_token(request: Request, auth_store = Depends(get_auth_store)):
	"""Revoke a session token (logout)."""
	# Extract token from cookie (could be any of: game:*, player:*, last_game, last_player)
	session_token = None
	for key, value in request.cookies.items():
		if key.startswith("game:") or key.startswith("player:") or key in ["last_game", "last_player"]:
			session_token = value
			break
	
	if not session_token:
		return JSONResponse({"error": "No session token found"}, status_code=400)
	
	try:
		await auth_store.invalidate_session(session_token)
	except SessionNotFound:
		logger.warning(f"Attempt to revoke non-existent session token")
		# Even if session not found, treat as successful logout (idempotent)
		pass
	except Exception as e:
		logger.error(f"Failed to revoke session token: {e}", exc_info=True)
		raise HTTPException(status_code=500, detail="Failed to revoke session token")
	
	return JSONResponse({"message": "Session revoked"})


