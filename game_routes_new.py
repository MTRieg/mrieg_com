from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from game_simulation import GAMES, PLAYERS, initialize_pieces, advance_simulation  # <-- import shared dictionary
from passwords import set_game_password, set_player_password, create_token, read_token, revoke_token
from passwords import game_passwords, player_passwords, session_tokens
import json
import random, string
import regex


router = APIRouter()

# --- Pydantic Models ---

class verifiedBaseModelPlus(BaseModel):
    player_id: str | None = None
    game_id: str | None = None
    last_player: str | None = None
    last_game: str | None = None

class BaseModelPlus(BaseModel):
    player_id: str | None = None
    game_id: str | None = None

class BaseModelPlusWithPassword(BaseModelPlus):
    game_password: str | None = None
    player_password: str | None = None

class GameSettings(BaseModel):
    max_players: int = 4
    board_size: int = 800
    board_shrink: int = 50
    turn_interval: int = 86400  # seconds

class CreateGameRequest(BaseModel):
    game_id: str
    password: str
    start_delay: int
    turn_interval: int
    settings: GameSettings | None = None

class CreatePlayerRequest(BaseModel):
    player_id: str
    password: str

class CreatePlayerAndJoinGameRequest(CreatePlayerRequest):
    game_id: str

#join game request is just baseModelPlus
#so is apply moves request and delete game request

class LeaveGameRequest(BaseModelPlus):
    player_leaving_game: str 
    #not neccessarily the same as player_id, who is making the request (e.g. admin kicking someone)

class SubmitTurnRequest(BaseModelPlus):
    turn_number: int
    actions: list[dict]



def check_credentials(inputs: BaseModelPlus, request: Request):
    outputs = verifiedBaseModelPlus(
        player_id=None,
        game_id=None,
        last_player=None,
        last_game=None,
    )

    cookies = request._cookies

    gameid_cookie = (
        cookies.get(f"game:{inputs.game_id}") if inputs.game_id else None
    )
    playerid_cookie = (
        cookies.get(f"player:{inputs.player_id}") if inputs.player_id else None
    )

    last_game_cookie = cookies.get("last_game")
    last_player_cookie = cookies.get("last_player")

    # validate tokens safely
    game_token = read_token(gameid_cookie) if gameid_cookie else None
    if game_token and game_token["game_id"] == inputs.game_id:
        outputs.game_id = inputs.game_id

    player_token = read_token(playerid_cookie) if playerid_cookie else None
    if player_token and player_token["player_id"] == inputs.player_id:
        outputs.player_id = inputs.player_id

    last_game_token = read_token(last_game_cookie) if last_game_cookie else None
    if last_game_token and last_game_token["game_id"]:
        outputs.last_game = last_game_token["game_id"]

    last_player_token = read_token(last_player_cookie) if last_player_cookie else None
    if last_player_token and last_player_token["player_id"]:
        outputs.last_player = last_player_token["player_id"]

    return outputs



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

# Allow: any Unicode letter/mark/number, spaces, plus a small, explicit set of name punctuation
VALID_NAME_RE = regex.compile(r"^[\p{L}\p{M}\p{N} .'\-`’·]+$", flags=regex.UNICODE)

def is_valid_name_regex(s: str) -> bool:
    if not s: 
        return False
    s = s.strip()
    if len(s) > 200:               # enforce a sensible max length
        return False
    return bool(VALID_NAME_RE.match(s))



#function to attach a cookie to the response
def append_cookie(response: JSONResponse, key: str, value: str, expires=2*24*60*60):
    response.set_cookie(key=key, value=value, httponly=False, expires=expires)  # 2 days
    return response

def censor_game(game):
    last_turn_time = game["state"]["last_turn_time"]
    if last_turn_time and isinstance(last_turn_time, datetime):
        last_turn_time = last_turn_time.isoformat()
    
    return {
        "creator": game.get("creator"),
        "turn_number": game["state"]["turn_number"],
        "last_turn_time": last_turn_time,
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

def copy_pieces_to_old_pieces(game):
    """Copies current pieces to old_pieces for comparison."""
    game["state"]["old_pieces"] = json.loads(json.dumps(game["state"]["pieces"]))
    game["state"]["old_turn_number"] = game["state"]["turn_number"]
    game["state"]["old_last_turn_time"] = game["state"]["last_turn_time"]

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




# --- Serve Knockout game HTML ---
@router.get("/knockout/game_dump", response_class=HTMLResponse)
def serve_info_dump(request: Request):
    encoded = jsonable_encoder(GAMES)
    return JSONResponse(encoded, status_code=200)

# --- Serve Knockout game HTML ---
@router.get("/knockout/player_dump", response_class=HTMLResponse)
def serve_info_dump_players(request: Request):
    encoded = jsonable_encoder(PLAYERS)
    return JSONResponse(encoded, status_code=200)

# --- Serve Knockout game HTML ---
@router.get("/knockout/passwords_dump", response_class=HTMLResponse)
def serve_info_dump_passwords(request: Request):
    data = {
        "player_passwords": player_passwords,
        "game_passwords": game_passwords,
        "session_tokens": session_tokens
    }
    encoded = jsonable_encoder(data)
    return JSONResponse(encoded, status_code=200)

@router.get("/knockout/save_dictionaries")
def save_dictionaries_to_file():
    """Save all game state, player data, and authentication data to JSON files."""
    try:
        with open("player_passwords.json", "w") as f:
            json.dump(player_passwords, f, indent=4, default=str)
        with open("game_passwords.json", "w") as f:
            json.dump(game_passwords, f, indent=4, default=str)
        with open("session_tokens.json", "w") as f:
            json.dump(session_tokens, f, indent=4, default=str)
        with open("games.json", "w") as f:
            json.dump(GAMES, f, indent=4, default=str)
        with open("players.json", "w") as f:
            json.dump(PLAYERS, f, indent=4, default=str)
        
        return JSONResponse({"message": "All dictionaries saved successfully"}, status_code=200)
    except IOError as e:
        return JSONResponse({"error": f"Failed to save files: {e}"}, status_code=500)


# --- Serve Knockout game HTML ---
@router.get("/knockout", response_class=HTMLResponse)
def serve_knockout_page(request: Request):
    game_id = request.query_params.get("game_id") or request.query_params.get("game")
    filename = "static/lobby_top.html"  # default
    
    if game_id and game_id in GAMES:
        game = GAMES[game_id]
        if game["state"]["pieces"]: #if the game has started
            # if request has a game_password param or a cookie for that game, 
            # send them to the game page, whether or not the params are correct
            print(request.query_params)
            print(request._cookies)
            if ("game_password" in request.query_params 
                or f"game:{game_id}" in request._cookies):
                filename = "static/game.html"
    
    with open(filename, "r") as f:
        return f.read()

#returns censored game state if valid gameid and cookie
@router.get("/api/game_state")
async def get_game_state(request: Request, game_id: str):
    if(not game_id or game_id == "null"):
        return JSONResponse({"error": "null game code"}, status_code=404)

    req = BaseModelPlus(game_id=game_id)
    creds = check_credentials(req, request)
    if(creds.game_id is None):
        return JSONResponse({"error": "Invalid credentials"}, status_code=403)
    game = GAMES.get(creds.game_id)
    if not game:
        return JSONResponse({"error": "Game not found"}, status_code=404)
    return censor_game(game)


#takes new gameid and password, creates game, returns game cookie
@router.post("/api/create_game")
async def create_game(req: CreateGameRequest):
    print("creating game")
    if not is_valid_name_regex(req.game_id):
        return JSONResponse({"error": "Invalid game ID"}, status_code=400)
    


    session_token = set_game_password(req.game_id, req.password)
    if(session_token is None):
        return JSONResponse({"error": "Game ID already exists"}, status_code=400)
    start_time = datetime.now(ZoneInfo("America/Toronto")) + timedelta(seconds=req.start_delay)
    settings = req.settings or GameSettings(turn_interval=req.turn_interval) 
    # SECURITY VULNERABILITY: sanitize settings input
    

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


    output = JSONResponse({
        "game_id": req.game_id,
        "invite_url": f"https://mrieg.com/games/knockout?game={req.game_id}",
        "start_time": start_time.isoformat(),
    })

    return append_cookie(output, "game:" + req.game_id, session_token)

#takes new playerid and password, creates player, returns player cookie
@router.post("/api/create_player")
async def create_player(req: CreatePlayerRequest):
    if not is_valid_name_regex(req.player_id):
        return JSONResponse({"error": "Invalid player ID"}, status_code=400)

    session_token = set_player_password(req.player_id, req.password)
    if(session_token is None):
        return JSONResponse({"error": "Player ID already exists"}, status_code=400)
    

    PLAYERS[req.player_id] = {"date_created": datetime.now(ZoneInfo("America/Toronto"))}


    out = JSONResponse({
        "player_id": req.player_id
    })

    return append_cookie(out, "player:" + req.player_id, session_token)

#takes new playerid, player password, existing gameid with game cookie, creates player and joins game
#sends back new cookie for player
@router.post("/api/register_for_game")
async def create_player_and_join_game(req: CreatePlayerAndJoinGameRequest):
    # Step 1: create player
    create_player_req = CreatePlayerRequest(
        player_id=req.player_id,
        password=req.password,
    )
    create_resp = await create_player(create_player_req)

    if isinstance(create_resp, JSONResponse) and create_resp.status_code >= 400:
        body = json.loads(create_resp.body)
        body["_source"] = "create_player"
        return JSONResponse(body, status_code=create_resp.status_code)

    # Step 2: join game
    join_req = BaseModelPlus(
        player_id=req.player_id,
        game_id=req.game_id,
    )
    credentials = verifiedBaseModelPlus(
        player_id=req.player_id,
        game_id=req.game_id
    )

    join_resp = await join_game_with_credentials(credentials, join_req)

    if isinstance(join_resp, JSONResponse) and join_resp.status_code >= 400:
        body = json.loads(join_resp.body)
        body["_source"] = "join_game"
        return JSONResponse(body, status_code=join_resp.status_code)

    output = JSONResponse(
        {
            "message": "Player created and joined game successfully",
            "player_id": req.player_id,
            "game_id": req.game_id,
            "start_time": GAMES[req.game_id]["start_time"].isoformat()
        },
        status_code=200,
    )


    # Copy cookies from create_resp to output
    if hasattr(create_resp, 'headers') and 'set-cookie' in create_resp.headers:
        output.headers.add_vary_header('set-cookie')
        for cookie in create_resp.headers.getlist('set-cookie'):
            output.headers.append('set-cookie', cookie)


    return output


#takes playerid and gameid and passwords, returns cookie if valid
@router.post("/api/create_session_cookie")
async def create_session_cookie(req: BaseModelPlusWithPassword):
    out = JSONResponse({"message": "Session cookies created"})

    token = create_token(game_id=req.game_id, game_password=req.game_password, 
                                     player_id=req.player_id, player_password=req.player_password)
    if(not token):
        return JSONResponse({"error": "Invalid game credentials"}, status_code=403)
    if req.game_id: # if game_id provided and token creation was successful
        out = append_cookie(out, "game:" + req.game_id, token)
        out = append_cookie(out, "last_game", token)
    if req.player_id: # if player_id provided and token creation was successful
        out = append_cookie(out, "player:" + req.player_id, token)
        out = append_cookie(out, "last_player", token)

    return out


#takes playerid and gameid (already authenticated), adds player to game if possible
@router.post("/api/join_game")
async def join_game(request: Request, req: BaseModelPlus):
    creds = check_credentials(req, request)
    print("joining game with creds:", creds)
    return await join_game_with_credentials(creds, req)
    

async def join_game_with_credentials(creds: verifiedBaseModelPlus, req: BaseModelPlus):
    if(creds.game_id is None or creds.player_id is None):
        return JSONResponse({"error": "Invalid credentials"}, status_code=403)
    
    game = GAMES.get(creds.game_id)
    if(game is None):
        return JSONResponse({"error": "Game not found"}, status_code=404)
    
    if(creds.player_id in game["players"]):
        return JSONResponse({"error": "Player already in game"}, status_code=409)
    
    if(len(game["players"]) >= game["settings"]["max_players"]):
        return JSONResponse({"error": "Game is full"}, status_code=400)
    
    # Add player to game
    game["players"][creds.player_id] = {
        "name": creds.player_id,
        "submitted_turn": False,
    }

    #if player is the first player, call them the creator
    if(len(game["players"]) == 1):
        game["creator"] = creds.player_id

    return JSONResponse({"message": "Player added to game", "game_state": censor_game(game)}, status_code=200)


@router.post("/api/leave_game")
async def leave_game(request: Request, req: LeaveGameRequest):
    creds = check_credentials(req, request)
    if(creds.game_id is None or creds.player_id is None):
        return JSONResponse({"error": "Invalid credentials"}, status_code=403)
    
    game = GAMES.get(creds.game_id)
    if(game is None):
        return JSONResponse({"error": "Game not found"}, status_code=404)
    
    if(req.player_leaving_game not in game["players"]):
        return JSONResponse({"error": "Player not in game"}, status_code=400)
    
    if(creds.player_id != req.player_leaving_game and creds.player_id != game["creator"]):
        return JSONResponse({"error": "Cannot remove other players unless you are the game creator"}, status_code=403)

    
    # Remove player from game
    del game["players"][req.player_leaving_game]

    return JSONResponse({"message": "Player removed from game", "game_state": censor_game(game)}, status_code=200)

@router.post("/api/delete_game")
async def delete_game(request: Request, req: BaseModelPlus):
    creds = check_credentials(req, request)
    if(creds.game_id is None or creds.player_id is None):
        return JSONResponse({"error": "Invalid credentials"}, status_code=403)
    game = GAMES.get(creds.game_id)
    if(game is None):
        return JSONResponse({"error": "Game not found"}, status_code=404)
    if(creds.player_id != game["creator"]):
        return JSONResponse({"error": "Only the game creator can delete the game"}, status_code=403)
    
    del GAMES[creds.game_id]
    return JSONResponse({"message": "Game deleted"}, status_code=200)


@router.post("/api/submit_turn")
async def submit_turn(request: Request, req: SubmitTurnRequest):
    creds = check_credentials(req, request)
    if(creds.game_id is None or creds.player_id is None):
        return JSONResponse({"error": "Invalid credentials"}, status_code=403)
    
    game = GAMES.get(creds.game_id)
    if(game is None):
        return JSONResponse({"error": "Game not found"}, status_code=404)
    
    if(creds.player_id not in game["players"]):
        return JSONResponse({"error": "Player not in game"}, status_code=400)
    
    if(req.turn_number != game["state"]["turn_number"]):
        return JSONResponse({"error": "Invalid turn number"}, status_code=400)

    """
    thing to eventually get back to, because this implementation is broken
    lastTurnTime = game["state"]["last_turn_time"]
    now = datetime.now(ZoneInfo("America/Toronto"))
    if(lastTurnTime is not None):
        next_turn_time = lastTurnTime + timedelta(seconds=game["settings"]["turn_interval"])
        if(now < lastTurnTime or next_turn_time > now):
            return JSONResponse({"error": "Turn submission window has not opened yet"}, status_code=400)
    """
    
    # Store submitted turn with actions
    game["players"][creds.player_id]["submitted_turn"] = {
        "turn_number": req.turn_number,
        "actions": req.actions,
    }

    # Check if all players have submitted their turns
    all_submitted = all(p["submitted_turn"] for p in game["players"].values())
    #if all_submitted:
        #todo: act like someone fasttracked the next turn

    return JSONResponse({"message": "Turn submitted", "game_state": censor_game(game)}, status_code=200)

@router.post("/api/apply_submitted_moves")
async def apply_submitted_moves(request: Request, req: BaseModelPlus):
    creds = check_credentials(req, request)
    if creds.game_id is None or creds.player_id is None:
        return JSONResponse({"error": "Invalid credentials"}, status_code=403)
    
    game = GAMES.get(creds.game_id)
    if not game:
        return JSONResponse({"error": "Game not found"}, status_code=404)
    
    if creds.player_id != game.get("creator"):
        return JSONResponse({"error": "Only the game creator can fasttrack the next turn"}, status_code=403)
    
    return await apply_submitted_moves_by_game_id(creds.game_id)


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


@router.post("/api/start_game")
async def start_game(request: Request, req: BaseModelPlus):
    creds = check_credentials(req, request)
    print(creds)
    if creds.game_id is None or creds.player_id is None:
        return JSONResponse({"error": "Invalid credentials"}, status_code=403)
    
    game = GAMES.get(creds.game_id)
    if not game:
        return JSONResponse({"error": "Game not found"}, status_code=404)
    
    if creds.player_id not in game["players"]:
        return JSONResponse({"error": "Player not in game"}, status_code=400)
    
    if creds.player_id != game.get("creator"):
        return JSONResponse({"error": "Only the game creator can start the game"}, status_code=403)
    
    if game["state"]["pieces"]:
        return JSONResponse({"error": "Game has already been started"}, status_code=400)
    
    now = datetime.now(ZoneInfo("America/Toronto"))
    initialize_pieces(game)
    initialize_colors(game)
    game["start_time"] = now  # mark as started
    
    return JSONResponse({
        "status": "started",
        "turn": game["state"]["turn_number"],
        "pieces": game["state"]["pieces"]
    }, status_code=200)


@router.post("/api/run_game")
async def run_game(request: Request, req: BaseModelPlus):
    creds = check_credentials(req, request)
    if creds.game_id is None or creds.player_id is None:
        return JSONResponse({"error": "Invalid credentials"}, status_code=403)
    
    game = GAMES.get(creds.game_id)
    if not game:
        return JSONResponse({"error": "Game not found"}, status_code=404)
    
    if creds.player_id not in game["players"]:
        return JSONResponse({"error": "Player not in game"}, status_code=400)
    
    if creds.player_id != game.get("creator"):
        return JSONResponse({"error": "Only the game creator can run the game simulation"}, status_code=403)
    
    if not any(p.get("submitted_turn") for p in game["players"].values()):
        return JSONResponse({"error": "No players have submitted moves yet"}, status_code=400)
    
    try:
        advance_simulation(game)
        return JSONResponse({
            "status": "advanced",
            "turn": game["state"]["turn_number"],
            "pieces": game["state"]["pieces"]
        }, status_code=200)
    except Exception as e:
        return JSONResponse({"error": f"Simulation failed: {e}"}, status_code=500)


@router.post("/api/apply_moves_and_run_game")
async def apply_moves_and_run_game(request: Request, req: BaseModelPlus):
    creds = check_credentials(req, request)
    if creds.game_id is None or creds.player_id is None:
        return JSONResponse({"error": "Invalid credentials"}, status_code=403)
    
    game = GAMES.get(creds.game_id)
    if not game:
        return JSONResponse({"error": "Game not found"}, status_code=404)
    
    if creds.player_id != game.get("creator"):
        return JSONResponse({"error": "Only the game creator can execute this action"}, status_code=403)
    
    if not any(p.get("submitted_turn") for p in game["players"].values()):
        return JSONResponse({"error": "No players have submitted moves yet"}, status_code=400)
    
    # Step 1: Apply submitted moves
    moves_result = await apply_submitted_moves_by_game_id(creds.game_id)
    
    if isinstance(moves_result, JSONResponse) and moves_result.status_code >= 400:
        return moves_result
    
    # Step 2: Run the game simulation
    try:
        advance_simulation(game)
        
        return JSONResponse({
            "status": "advanced",
            "turn": game["state"]["turn_number"],
            "pieces": game["state"]["pieces"]
        }, status_code=200)
    except Exception as e:
        return JSONResponse({"error": f"Simulation failed: {e}"}, status_code=500)






