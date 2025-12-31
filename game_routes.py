from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from game_simulation import GAMES, PLAYERS, initialize_pieces, advance_simulation  # <-- import shared dictionary
from passwords import set_game_password, set_player_password, create_token, read_token, revoke_token
import json
import random, string
import re


router = APIRouter()



# --- Pydantic Models ---
class GameSettings(BaseModel):
    max_players: int = 4
    board_size: int = 800
    board_shrink: int = 50
    turn_interval: int = 86400  # seconds

class CreateGameRequest(BaseModel):
    game_id: str
    game_password: str
    start_delay: int
    turn_interval: int
    settings: GameSettings | None = None

class CreatePlayerRequest(BaseModel):
    player_id: str
    player_password: str

class JoinGameRequest(BaseModel):
    game_id: str
    player_id: str

class LeaveGameRequest(BaseModel):
    game_id: str
    player_id: str
    requester_id: str

class SubmitTurnRequest(BaseModel):
    game_id: str
    player_id: str
    turn_number: int
    actions: list[dict]

class ApplyMovesRequest(BaseModel):
    game_id: str
    player_id: str

class DeleteGameRequest(BaseModel):
    game_id: str
    player_id: str


# --- Serve Knockout game HTML ---
@router.get("/knockout", response_class=HTMLResponse)
def serve_knockout_page(request: Request):
    game_id = request.query_params.get("game_id")
    filename = "static/lobby.html"  # default
    
    print(request.query_params)
    if game_id:
        print(game_id)

    if game_id and game_id in GAMES:
        game = GAMES[game_id]
        start_time = game.get("start_time")
        

        # Check that the game has a start_time and that it's in the past or now
        if start_time and isinstance(start_time, datetime):
            print(start_time, datetime.now(ZoneInfo("America/Toronto")))
            if start_time <= datetime.now(ZoneInfo("America/Toronto")):
                if(len(game["state"]["pieces"]) == 0):
                    start_game(game, datetime.now(ZoneInfo("America/Toronto")))
                filename = "static/game.html"
                

    with open(filename, "r") as f:
        return f.read()

# currently unused
def format_json(Json_string):
    try:
        data = json.loads(json.string)
        return json.dumps(data, indent=4, ensure_ascii=False)
    except json.JSONDecoderError as e:
        return f"invalid JSON: {e}"


def create_id():

    digits = ''.join(random.choices(string.digits, k=4))
    letters = ''.join(random.choices(string.ascii_lowercase, k=4))
    return (digits + letters)






# --- Serve Knockout game HTML ---
@router.get("/knockout/game_dump", response_class=HTMLResponse)
def serve_info_dump(request: Request):
    encoded = jsonable_encoder(GAMES)
    return JSONResponse(encoded, status_code=200)

# --- API ROUTES ---


@router.post("/api/start_or_run_game")
async def start_or_run_game(game_id: str, player_id: str):
    """Starts a game if not started, or runs the simulation if already started."""
    if game_id not in GAMES:
        raise HTTPException(status_code=404, detail="Game not found")

    game = GAMES[game_id]
    now = datetime.now(ZoneInfo("America/Toronto"))
    start_time = game.get("start_time")

    if player_id not in game["players"]: 
        raise HTTPException(status_code=404, detail="PlayerID not found")
    
    if game["players"][player_id]["name"] != game["creator"]:
        raise HTTPException(status_code=403, detail="Only the creator can start the game early")

    # Case 1: game hasn't started yet
    if start_time and now < start_time:
        return start_game(game, now)
        

    # Case 2: game already started -> run simulation
    return run_game(game)


def start_game(game, now=None):
    if now is None:
        now = datetime.now(ZoneInfo("America/Toronto"))
    initialize_pieces(game)
    initialize_colors(game)
    game["start_time"] = now  # mark as started
    return JSONResponse({
        "status": "started",
        "turn": game["state"]["turn_number"],
        "pieces": game["state"]["pieces"]
    })

def run_game(game):
    try:
        advance_simulation(game)
        return JSONResponse({
            "status": "advanced",
            "turn": game["state"]["turn_number"],
            "pieces": game["state"]["pieces"]
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation failed: {e}")


def initialize_colors(game):
    """Assigns a distinct color to each player and stores it in game['players'][pid]['color']."""
    base_colors = [
        "#FF0000", "#00FF00", "#0000FF"             , "#FF00FF", "#00FFFF",
        "#FFA500", "#800080", "#008000", "#FFC0CB", "#A52A2A", "#808000",
        "#000080", "#800000", "#008080", "#C0C0C0", "#FFD700", "#DC143C",
        "#4682B4", "#DA70D6", "#ADFF2F", "#40E0D0", "#FA8072", "#7FFF00",
        "#1E90FF", "#BA55D3", "#FF8C00", "#B0C4DE", "#2E8B57", "#F08080",
        "#00CED1", "#FF1493", "#ADFF2F", "#FF4500", "#9ACD32", "#708090",
        "#20B2AA", "#CD5C5C", "#F0E68C", "#9932CC", "#8FBC8F", "#E9967A",
        "#B22222", "#5F9EA0", "#66CDAA", "#BC8F8F", "#556B2F", "#D2691E",
        "#483D8B", "#FF6347", "#6495ED", "#E6E6FA", "#BDB76B", "#A9A9A9"
    ]

    for i, pid in enumerate(game["players"].keys()):
        game["players"][pid]["color"] = base_colors[i % len(base_colors)]



@router.post("/api/create_game")
async def create_game(req: CreateGameRequest):
    if not is_valid_name_regex(req.game_id):
        return JSONResponse({"error": "Invalid game ID"}, status_code=400)

    session_token = set_game_password(req.game_id, req.game_password)
    if(session_token is None):
        return JSONResponse({"error": "Game ID already exists"}, status_code=400)
    start_time = datetime.now(ZoneInfo("America/Toronto")) + timedelta(seconds=req.start_delay)
    settings = req.settings or GameSettings(turn_interval=req.turn_interval)
    

    GAMES[req.game_id] = {
        "settings": settings.dict(),
        "players": {},
        "state": {
            "turn_number": 0,
            "last_turn_time": None,
            "pieces": [],
        },
        "start_time": start_time,
    }

    return {
        "game_id": req.game_id,
        "invite_url": f"https://mrieg.com/games/knockout?game={req.game_id}",
        "start_time": start_time.isoformat(),
        "session_token": session_token
    }

@router.post("/api/create_player")
async def create_player(req: CreatePlayerRequest):
    if not is_valid_name_regex(req.player_id):
        return JSONResponse({"error": "Invalid player ID"}, status_code=400)

    session_token = set_player_password(req.player_id, req.player_password)
    if(session_token is None):
        return JSONResponse({"error": "Player ID already exists"}, status_code=400)
    

    PLAYERS[req.player_id] = {}

    return {
        "player_id": req.player_id
    }





@router.post("/api/join_game")
async def join_game(req: JoinGameRequest):
    # todo: why the heck is it using "session_token"

    if (req.cookies.get("session_token")):
        token_data = read_token(req.cookies.get("session_token"))
        if token_data is None:
            return JSONResponse({"error": "Invalid session token"}, status_code=403)
        if token_data["game_id"] != req.game_id:
            return JSONResponse({"error": "Session token does not match game ID"}, status_code=403)
        #if token_data["player_id"] is not None:
            # this should not happen as we are joining a game, not rejoining
            # req.player_id = token_data["player_id"]
    game = GAMES.get(req.game_id)


    if not game:
        return JSONResponse({"error": "Game not found"}, status_code=404)
    

    if req.player_id in (game["players"]):
        response = JSONResponse("Player ID already in use in this game", status_code=403)

        # once I update the frontend to use rejoin API, this should be an error instead
        response = JSONResponse({"player_id": req.player_id, "message": "Welcome back!"}, status_code=202)
        if req.player_id:
            return append_game_cookie(response, req.game_id, req.player_id)

    if len(game["players"]) >= game["settings"]["max_players"]:
        return JSONResponse({"error": "Game full"}, status_code=403)
    
    
    player_id = create_id()
    game["players"][player_id] = {"name": req.player_name, "submitted_turn": None}

    return {
        "status": "joined",
        "player_id": player_id,
        "creator_id": next(pid for pid, pdata in game["players"].items() if pdata["name"] == game["creator"]),
        "game_state": {
            "start_time": game["start_time"],
            "players": list(p["name"] for p in game["players"].values()),
            "board_state": game["state"]["pieces"]
        }
    }

@router.post("/api/rejoin_game")
async def rejoin_game(req: JoinGameRequest):
    game = GAMES.get(req.game_id)
    if not game:
        return JSONResponse({"error": "Game not found"}, status_code=404)

    #if the name you give is already in the game, return a welcome back message and give them their player id cookie
    if req.player_name in (list(p["name"] for p in game["players"].values())):
        player_id = next((pid for pid, p in game["players"].items() if p["name"] == req.player_name), None)
        response = JSONResponse({"player_id": player_id, "message": "Welcome back!"}, status_code=202)
        if player_id:
            return append_game_cookie(response, req.game_id, player_id)
    return JSONResponse({"error": "Player name not found in game"}, status_code=404)

@router.post("/api/leave_game")
async def leave_game(req: LeaveGameRequest):
    game = GAMES.get(req.game_id)
    if not game:
        return JSONResponse({"error": "Game not found"}, status_code=404)

    #if the id given is not already in the game, return error
    if not req.player_id in (game["players"]):
        return JSONResponse({"error": "deleting a nonexistent player"}, status_code=404)
    
    if not (req.player_id == req.requester_id or game["players"][req.requester_id]["name"] == game["creator"]):
        return JSONResponse({"error": "only that player or the game creator can remove themselves from the game"}, status_code=403)



    del game["players"][req.player_id]
    return JSONResponse({"success": "player " + req.player_id + " removed from the game."}, status_code=200)
    

@router.post("/api/delete_game")
async def delete_game(req: DeleteGameRequest):
    game = GAMES.get(req.game_id)
    if not game:
        return JSONResponse({"error": "Game not found"}, status_code=404)

    
    if not (game["players"][req.requester_id] and game["players"][req.requester_id]["name"] == game["creator"]):
        return JSONResponse({"error": "only the game creator can delete the game"}, status_code=403)



    del game
    return JSONResponse({"success": "game deleted"}, status_code=200)
    




# Allow: any Unicode letter/mark/number, spaces, plus a small, explicit set of name punctuation
VALID_NAME_RE = re.compile(r"^[\p{L}\p{M}\p{N} .'\-`’·]+$", flags=re.UNICODE)

def is_valid_name_regex(s: str) -> bool:
    if not s: 
        return False
    s = s.strip()
    if len(s) > 200:               # enforce a sensible max length
        return False
    return bool(VALID_NAME_RE.match(s))


#function to give the user a cookie when they join a game containing their player id and game id
def append_game_cookie(response: JSONResponse, game_id: str, player_id: str):
    cookie_value = f"{game_id}:{player_id}"
    #todo: make code still work if there aren't existing cookies
    existing_cookies = getattr(response, "cookies", {}).get("game_info", "")
    if existing_cookies:
        cookie_value = f"{existing_cookies},{cookie_value}"
    response.set_cookie(key="game_info", value=cookie_value, httponly=True, expires=30*24*60*60)  # 1 month
    return response


def censor_game(game):
    return {
        "creator": game["creator"],
        "turn_number": game["state"]["turn_number"],
        "last_turn_time": game["state"]["last_turn_time"],
        "board_size": game["settings"]["board_size"],
        "board_shrink": game["settings"]["board_shrink"],
        "players": {pid: {"name": p["name"], "color": p.get("color", ""), "submitted_turn": ("waiting" if not p.get("submitted_turn") else "")} for pid, p in game["players"].items()},
        "pieces": game["state"]["pieces"],
        "old_pieces": game["state"].get("old_pieces", []),
        "next_turn_deadline": (
            game["start_time"]
            + timedelta(seconds=game["settings"]["turn_interval"] * (game["state"]["turn_number"] + 1))
        ).isoformat(),
    }
    

@router.get("/api/game_state")
async def get_game_state(game_id: str):
    game = GAMES.get(game_id)
    if not game:
        return JSONResponse({"error": "Game not found"}, status_code=404)
    return censor_game(game)

    

@router.get("/api/player_state")
async def get_player_state(player_id: str):
    result = {}
    for game_id, game in GAMES.items():
        if player_id in game["players"]:
            result[game_id] = censor_game(game)
    return result



@router.post("/api/submit_turn")
async def submit_turn(req: SubmitTurnRequest):
    print("recieved submit turn request\n")
    game = GAMES.get(req.game_id)
    if not game:
        return JSONResponse({"error": "Game not found"}, status_code=404)
    player = game["players"].get(req.player_id)
    if not player:
        return JSONResponse({"error": "Player not found"}, status_code=404)

    if any("pieceid" not in item for item in req.actions):
        print("There was a mistake somewhere, the actions did not have piece ids ", player);
    

    player["submitted_turn"] = {
        "turn_number": req.turn_number,
        "actions": req.actions,
    }

    return {"status": "turn submitted", "turn_number": req.turn_number}


@router.post("/api/apply_submitted_moves")
async def apply_submitted_moves(req: ApplyMovesRequest):
    #check that player created the game
    game = GAMES.get(req.game_id)
    if not game:
        return JSONResponse({"error": "Game not found"}, status_code=404)
    player = game["players"].get(req.player_id)["name"]
    if not player:
        return JSONResponse({"error": "Player not found"}, status_code=404)
    creator = game.get("creator")
    if player != creator:
        return JSONResponse({"error": "Only the game creator can fasttrack the next turn"}, status_code=403)
    return await apply_submitted_moves_by_game_id(req.game_id)


async def apply_submitted_moves_by_game_id(game_id):
    """
    Apply all submitted moves for the current turn by updating piece vx/vy.
    Uses action['pieceid'] as a unique piece identifier, not an array index.
    """
    game = GAMES.get(game_id)
    if not game:
        return JSONResponse({"error": "Game not found"}, status_code=404)

    current_turn = game["state"].get("turn_number", 0)
    pieces = game["state"].get("pieces", [])
    updates = []

    # Pre-index pieces by their unique pieceid for fast lookup
    pieces_by_id = {p.get("pieceid"): p for p in pieces}

    for pid, player in game["players"].items():
        submitted = player.get("submitted_turn")
        if not submitted:
            continue
        if submitted.get("turn_number") != current_turn:
            submitted = None
            continue

        for action in submitted.get("actions", []):
            pieceid = action.get("pieceid")
            if pieceid is None:
                action = None
                continue

            piece = pieces_by_id.get(pieceid)
            if not piece:
                # No piece with this ID -> skip
                continue

            # Ensure piece belongs to the player
            if piece.get("owner") != pid:
                continue

            # Apply velocities if present
            vx = action.get("vx")
            vy = action.get("vy")
            if vx is not None:
                piece["vx"] = vx
            if vy is not None:
                piece["vy"] = vy

            updates.append({
                "pieceid": pieceid,
                "owner": piece.get("owner"),
                "vx": piece.get("vx"),
                "vy": piece.get("vy"),
            })

    copy_pieces_to_old_pieces(game)

    return {
        "status": "applied",
        "turn": current_turn,
        "updated_count": len(updates),
        "updates": updates,
    }


def copy_pieces_to_old_pieces(game):
    """Copies current pieces to old_pieces for comparison."""
    game["state"]["old_pieces"] = json.loads(json.dumps(game["state"]["pieces"]))
    game["state"]["old_turn_number"] = game["state"]["turn_number"]
    game["state"]["old_last_turn_time"] = game["state"]["last_turn_time"]
