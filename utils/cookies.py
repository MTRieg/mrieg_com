"""Cookie helpers for FastAPI request/response handling.

Small convenience wrappers around FastAPI `Request` and `Response` cookie
APIs used by route handlers and tests.
"""
from typing import Optional, Any, Dict
from fastapi import Request, Response
from stores import SessionNotFound, SessionExpired


class UnauthorizedException(Exception):
	"""Raised when credentials are provided but fail validation."""
	pass


def set_cookie(response: Response, key: str, value: str, *, expires: int = 2 * 24 * 60 * 60, httponly: bool = False) -> Response:
	"""Set a cookie on the given `Response` and return it.

	- `expires` is in seconds (defaults to 2 days).
	- `httponly` defaults to False for client-readable tokens in this app.
	"""
	response.set_cookie(key=key, value=value, httponly=httponly, max_age=expires, expires=expires)
	return response


def get_cookie(request: Request, key: str) -> Optional[str]:
	"""Return the cookie value from a `Request`, or `None` if missing."""
	return request.cookies.get(key)


def delete_cookie(response: Response, key: str) -> Response:
	"""Delete a cookie by name on the `Response` and return it."""
	response.delete_cookie(key)
	return response


def append_cookie(response: Response, key: str, value: str, *, expires: int = 2 * 24 * 60 * 60) -> Response:
	"""Compatibility wrapper used elsewhere in the project."""
	return set_cookie(response, key, value, expires=expires, httponly=False)


def validate_token(session_token: str, auth_store: Any) -> Optional[Dict[str, Any]]:
	"""
	Validate a session token using the AuthStore.

	Args:
		session_token: The session token string to validate
		auth_store: An AuthStore instance (e.g., SqliteAuthStore)

	Returns:
		A dict with 'game_id' and 'player_id' keys if valid, None otherwise.
	"""
	import asyncio
	try:
		# Call the async validate_session_token synchronously
		result = asyncio.run(auth_store.validate_session_token(session_token))
		if result:
			return {
				"game_id": result.get("game_id"),
				"player_id": result.get("player_id"),
			}
	except (SessionExpired, SessionNotFound):
		# Token validation failed
		pass
	return None


async def check_credentials(
	request: Request,
	game_id: Optional[str] = None,
	player_id: Optional[str] = None,
	auth_store: Optional[Any] = None,
) -> Dict[str, Optional[str]]:
	"""
	Validate game and player credentials from cookies using an AuthStore.

	Args:
		request: FastAPI Request object
		game_id: Optional game ID to validate
		player_id: Optional player ID to validate
		auth_store: Optional AuthStore instance. If provided, tokens will be validated.
			If not provided, this function returns empty results.

	Returns:
		dict: {
			"game_id": validated_game_id or None,
			"player_id": validated_player_id or None,
			"last_game": last_game_id or None,
			"last_player": last_player_id or None,
		}
	"""
	results = {
		"game_id": None,
		"player_id": None,
		"last_game": None,
		"last_player": None,
	}

	# If no auth_store provided, just return empty results (no validation possible)
	if auth_store is None:
		return results

	# Check game credential
	if game_id:
		game_cookie = get_cookie(request, f"game:{game_id}")
		if game_cookie:
			token_data = await auth_store.validate_session_token(game_cookie)
			if token_data and token_data.get("game_id") == game_id:
				results["game_id"] = game_id
			else:
				# Cookie exists but failed validation
				raise UnauthorizedException(f"Invalid credentials for game {game_id}")
		else:
			# Game ID requested but no cookie found
			raise UnauthorizedException(f"No credentials found for game {game_id}")

	# Check player credential
	if player_id:
		player_cookie = get_cookie(request, f"player:{player_id}")
		if player_cookie:
			token_data = await auth_store.validate_session_token(player_cookie)
			if token_data and token_data.get("player_id") == player_id:
				results["player_id"] = player_id
			else:
				# Cookie exists but failed validation
				raise UnauthorizedException(f"Invalid credentials for player {player_id}")
		else:
			# Player ID requested but no cookie found
			raise UnauthorizedException(f"No credentials found for player {player_id}")

	# Check last_game and last_player (for session recovery)
	last_game_cookie = get_cookie(request, "last_game")
	if last_game_cookie:
		token_data = await auth_store.validate_session_token(last_game_cookie)
		if token_data and token_data.get("game_id"):
			results["last_game"] = token_data["game_id"]

	last_player_cookie = get_cookie(request, "last_player")
	if last_player_cookie:
		token_data = await auth_store.validate_session_token(last_player_cookie)
		if token_data and token_data.get("player_id"):
			results["last_player"] = token_data["player_id"]

	return results


