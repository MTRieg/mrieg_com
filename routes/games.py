from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse, HTMLResponse
from workers.tasks import start_game as start_game_task
import bcrypt
import os
import logging

from models import (
	CreateGameRequest,
	SubmitTurnRequest,
	ApplyMovesAndRunGameRequest,
	BaseModelPlus,
)
from stores import (
	get_game_store, 
	get_auth_store, 
	GameNotFound, 
	PlayerNotFound, 
	GameAlreadyExists,
	GameFull,
	TurnMismatch,
	InvalidState,
	CreatorOnlyAction,
	SimulationError,
	UnexpectedResult,
)
from utils.cookies import check_credentials, UnauthorizedException
from utils.validation import is_valid_name
from .auth import create_session_and_append_cookies, _hash_password
from . import games_helpers

logger = logging.getLogger(__name__)

router = APIRouter()




@router.get("/knockout", response_class=HTMLResponse)
async def serve_knockout_page(request: Request, game_id: str | None = None, store = Depends(get_game_store)):
	if not game_id:
		game_id = request.query_params.get("game_id") or request.query_params.get("game")
	
	filename = "static/lobby_top.html"  # default
	
	if game_id:
		try:
			await store.get_game_summary(game_id)  # Verify game exists
			pieces = await store.get_pieces(game_id)
			# If game has started (has pieces) and user has access (which we are not validating here), show game page
			if pieces:
				if ("game_password" in request.query_params or f"game:{game_id}" in request.cookies):
					filename = "static/game.html"
		except GameNotFound:
			pass  # Game not found, use default lobby page
	
	with open(filename, "r") as f:
		return f.read()


# --- API endpoints (stubs) ---
@router.get("/api/game_state")
async def get_game_state(request: Request, game_id: str, store = Depends(get_game_store), auth_store = Depends(get_auth_store)):
	try:
		creds = await check_credentials(request, game_id=game_id, auth_store=auth_store)
	except UnauthorizedException as e:
		raise HTTPException(status_code=401, detail=str(e))
	
	try:
		game_state = await store.get_game(creds["game_id"])
		games_helpers.censor_game_state(game_state)
		return JSONResponse(content=game_state)
	except GameNotFound:
		raise HTTPException(status_code=404, detail="Game not found")
	




@router.post("/api/create_game")
async def create_game(request: Request, req: CreateGameRequest, store = Depends(get_game_store), auth_store = Depends(get_auth_store)):
	import logging
	logger = logging.getLogger(__name__)

	if(not is_valid_name(req.game_id)):
		raise HTTPException(status_code=400, detail="Invalid game ID format. (Use only letters, numbers, spaces, and .'-`’· characters.)")

	
	# Create game with settings from request (or use defaults)
	settings = req.settings.dict() if req.settings else {}
	
	try:
		

		logger.info(f"Creating game {req.game_id}")
        
		# Hash password and create game with settings from request (and password)
		salt, hashed = _hash_password(req.password)

		# Store layer: persist game to database, returns scheduled start_time
		start_time = await store.create_game(
			req.game_id,
			max_players=settings.get("max_players", 4),
			board_size=settings.get("board_size", 800),
			board_shrink=settings.get("board_shrink", 50),
			turn_interval=settings.get("turn_interval", 86400),
			start_delay=req.start_delay,
			game_salt=salt,
			game_hashed=hashed,
		)
		logger.info(f"Game {req.game_id} created successfully, scheduled for {start_time}")

		# Infrastructure layer: schedule background task using the start_time from store
		try:
			# Explicitly pass broker URL to ensure it uses the correct Redis service
			broker_url = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
			start_game_task.apply_async(
				args=[req.game_id],  
				eta=start_time,
				ignore_result=True,
				broker=broker_url
			)
			logger.info(f"Scheduled start_game task for {req.game_id} at {start_time}")
		except Exception as exc:
			# Log but don't fail game creation if scheduling fails
			logger.error(f"Failed to schedule automatic game start: {exc}")

		output = JSONResponse(status_code=201, content={"game_id": req.game_id})
		try:
			# Create a session token tied to this game so the creator has a game cookie
			output = await create_session_and_append_cookies(output, auth_store, game_id=req.game_id)
		except Exception:
			# If cookie creation fails, log and still return success creating the game
			pass

		return output
	except GameAlreadyExists as exc:
		logger.info(f"Attempt to create existing game {req.game_id}: {exc}")
		raise HTTPException(status_code=409, detail=str(exc))
	except Exception as exc:
		logger.error(f"Unexpected error creating game: {exc}", exc_info=True)
		raise HTTPException(status_code=500, detail=f"Server error: {str(exc)}")


@router.post("/api/join_game")
async def join_game(request: Request, req: BaseModelPlus, store = Depends(get_game_store), auth_store = Depends(get_auth_store)):
	try:
		creds = await check_credentials(request, game_id=req.game_id, player_id=req.player_id, auth_store=auth_store)
		player_id = creds["player_id"]
		game_id = creds["game_id"]
	except UnauthorizedException as e:
		raise HTTPException(status_code=401, detail=str(e))
	
	try:
		result = await games_helpers.join_game(store, game_id, player_id)
		return JSONResponse(content=result)
	except GameNotFound:
		raise HTTPException(status_code=404, detail="Game not found")
	except Exception as exc:
		raise HTTPException(status_code=400, detail=str(exc))

@router.post("/api/leave_game")
async def leave_game(request: Request, req: BaseModelPlus, store = Depends(get_game_store), auth_store = Depends(get_auth_store)):
	try:
		creds = await check_credentials(request, game_id=req.game_id, player_id=req.player_id, auth_store=auth_store)
		player_id = creds["player_id"]
		game_id = creds["game_id"]
	except UnauthorizedException as e:
		raise HTTPException(status_code=401, detail=str(e))
	
	try:
		result = await games_helpers.leave_game(store, game_id, player_id, owner_id=None)
		return JSONResponse(content=result)
	except GameNotFound:
		raise HTTPException(status_code=404, detail="Game not found")
	except PlayerNotFound:
		raise HTTPException(status_code=404, detail="Player not in game")
	except Exception as exc:
		raise HTTPException(status_code=400, detail=str(exc))


@router.post("/api/delete_game")
async def delete_game(request: Request, req: BaseModelPlus, store = Depends(get_game_store), auth_store = Depends(get_auth_store)):
	try:
		creds = await check_credentials(request, game_id=req.game_id, player_id=req.player_id, auth_store=auth_store)
		owner_id = creds["player_id"]
		game_id = creds["game_id"]
	except UnauthorizedException as e:
		raise HTTPException(status_code=401, detail=str(e))
	
	try:
		result = await games_helpers.delete_game(store, game_id, player_id=None, owner_id=owner_id)
		return JSONResponse(content=result)
	except GameNotFound:
		raise HTTPException(status_code=404, detail="Game not found")
	except Exception as exc:
		raise HTTPException(status_code=403, detail=str(exc))

@router.post("/api/submit_turn")
async def submit_turn(request: Request, req: SubmitTurnRequest, store = Depends(get_game_store), auth_store = Depends(get_auth_store)):
	try:
		creds = await check_credentials(request, game_id=req.game_id, player_id=req.player_id, auth_store=auth_store)
		player_id = creds["player_id"]
		owner_id = creds["player_id"]
		game_id = creds["game_id"]
	except UnauthorizedException as e:
		raise HTTPException(status_code=401, detail=str(e))
	
	try:
		result = await games_helpers.submit_turn(store, game_id, player_id, req.turn_number, req.actions, owner_id=owner_id)
		return JSONResponse(content=result)
	except GameNotFound:
		raise HTTPException(status_code=404, detail="Game not found")
	except PlayerNotFound:
		raise HTTPException(status_code=404, detail="Player not in game")
	except Exception as exc:
		raise HTTPException(status_code=400, detail=str(exc))

@router.post("/api/start_game")
async def start_game(request: Request, req: BaseModelPlus, store = Depends(get_game_store), auth_store = Depends(get_auth_store)):
	try:
		creds = await check_credentials(request, game_id=req.game_id, player_id=req.player_id, auth_store=auth_store)
		owner_id = creds["player_id"]
		game_id = creds["game_id"]
	except UnauthorizedException as e:
		raise HTTPException(status_code=401, detail=str(e))
	
	try:
		result = await games_helpers.start_game(store, game_id, owner_id=owner_id)
		return JSONResponse(content=result)
	except GameNotFound:
		logger.warning(f"Attempt to start non-existent game: {game_id}")
		raise HTTPException(status_code=404, detail="Game not found")
	except TurnMismatch as exc:
		logger.info(f"Attempt to start already-started game {game_id}: {exc}")
		raise HTTPException(status_code=409, detail=f"Game already started: {str(exc)}")
	except InvalidState as exc:
		logger.error(f"Invalid game state for game {game_id}: {exc}")
		raise HTTPException(status_code=400, detail=f"Invalid game state: {str(exc)}")
	except Exception as exc:
		logger.error(f"Failed to start game {game_id}: {exc}", exc_info=True)
		raise HTTPException(status_code=400, detail=str(exc))

@router.post("/api/apply_moves_and_run_game")
async def apply_moves_and_run_game(request: Request, req: ApplyMovesAndRunGameRequest, store = Depends(get_game_store), auth_store = Depends(get_auth_store)):
	try:
		creds = await check_credentials(request, game_id=req.game_id, auth_store=auth_store)
		game_id = creds["game_id"]
	except UnauthorizedException as e:
		raise HTTPException(status_code=401, detail=str(e))
	try:
		# Client provides their view of current turn to prevent race conditions
		# If turn has advanced server-side, store will raise TurnMismatch
		result = await games_helpers.apply_moves_and_run_game(store, game_id, turn_number=req.turn_number)
		return JSONResponse(content=result)
	except GameNotFound:
		logger.warning(f"Attempt to run turn on non-existent game: {game_id}")
		raise HTTPException(status_code=404, detail="Game not found")
	except TurnMismatch as exc:
		logger.info(f"Turn mismatch for game {game_id}: {exc}")
		raise HTTPException(status_code=409, detail=f"Turn mismatch: {str(exc)}")
	except InvalidState as exc:
		logger.error(f"Invalid game state for game {game_id}: {exc}")
		raise HTTPException(status_code=400, detail=f"Invalid game state: {str(exc)}")
	except SimulationError as exc:
		logger.error(f"Simulation error for game {game_id}: {exc}")
		raise HTTPException(status_code=500, detail="Simulation failed")
	except UnexpectedResult as exc:
		logger.error(f"Unexpected result for game {game_id}: {exc}")
		raise HTTPException(status_code=500, detail="Internal server error")
	except Exception as exc:
		logger.error(f"Unexpected error running turn for game {game_id}: {exc}", exc_info=True)
		raise HTTPException(status_code=500, detail="Internal server error")

