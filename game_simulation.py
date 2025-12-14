# game_simulation.py
import json
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo
import random
import math
import shutil
import os
from game_initial import GAMES_INITIAL

GAMES = GAMES_INITIAL  # example game for testing


# --- Helper: initialize starting positions ---

def initialize_pieces(game, pieces_per_player=4):
    """Place each player's pieces randomly without overlap or proximity to board edges."""
    board_size = game["settings"]["board_size"]
    players = list(game["players"])
    pieces = []
    piece_radius = 30  # adjust if needed
    edge_buffer = 50

    def is_valid_position(x, y):
        # must be far enough from edges
        if x < edge_buffer - board_size or x > board_size - edge_buffer:
            return False
        if y < edge_buffer - board_size or y > board_size - edge_buffer:
            return False
        # must not overlap existing pieces
        for p in pieces:
            dx = p["x"] - x
            dy = p["y"] - y
            if math.hypot(dx, dy) < 2 * piece_radius + 5:
                return False
        return True

    for i in range(len(players)):
        player = players[i]
        for j in range(pieces_per_player):
            for _ in range(1000):  # placement attempts
                x = (random.random()-0.5) * (board_size - edge_buffer)
                y = (random.random()-0.5) * (board_size - edge_buffer)
                if is_valid_position(x, y):
                    pieces.append({
                        "owner": player,
                        "pieceid": i * pieces_per_player + j,
                        "x": x,
                        "y": y,
                        "vx": 0,
                        "vy": 0,
                    })
                    break
            else:
                print(f"Warning: could not place piece for {player}")

    game["state"]["pieces"] = pieces
    game["state"]["turn_number"] = 0
    game["state"]["last_turn_time"] = datetime.now(ZoneInfo("America/Toronto"))



# --- Helper: advance simulation ---
# only updates game["state"]["pieces"] based on existing vx/vy in those fields
def advance_simulation(game):
    """Run physics and update the game state."""
    board_size = game["settings"]["board_size"]
    board_shrink = game["settings"]["board_shrink"]
    pieces_before = game["state"]["pieces"]

    #filter out pieces where status is "out"
    pieces_before_filtered = [p for p in pieces_before if p.get("status") != "out"]
    pieces_before_out = [p for p in pieces_before if p.get("status") == "out"]


    # Run JS simulation
    try:
        new_state = run_js_simulation(pieces_before_filtered, board_before=board_size, board_after=board_size-board_shrink)
    except Exception as e:
        print(f"Error from python: {e}")
        raise RuntimeError("something went wrong")
        

    game["state"]["pieces"] = new_state.get("pieces", []) + pieces_before_out
    game["state"]["turn_number"] += 1
    game["state"]["last_turn_time"] = datetime.now(ZoneInfo("America/Toronto"))
    game["settings"]["board_size"] -= board_shrink
    
    for player in game["players"]:
        game["players"][player].pop("submitted_turn", None)

    return



def _sanitize_obj(obj, depth=0, max_depth=10):
    """Recursively validate/sanitize objects from untrusted JSON.
    - Rejects keys that can cause prototype pollution.
    - Enforces simple type expectations (dict/list/primitive).
    - Prevents extremely deep nesting.
    """
    if depth > max_depth:
        raise ValueError("Input too deeply nested")
    if isinstance(obj, dict):
        clean = {}
        for k, v in obj.items():
            if not isinstance(k, str):
                raise ValueError("Invalid key type")
            # Disallow prototype keys
            if k in ("__proto__", "prototype", "constructor"):
                raise ValueError(f"Disallowed key: {k}")
            # Optional: restrict allowed keys further here
            clean[k] = _sanitize_obj(v, depth + 1, max_depth)
        return clean
    elif isinstance(obj, list):
        return [_sanitize_obj(v, depth + 1, max_depth) for v in obj]
    elif isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    else:
        raise ValueError("Unsupported value type in input")


def run_js_simulation(pieces, board_before=800, board_after=700, *,
                      max_input_bytes=200_000, timeout_s=10):
    print("running simulation\n")
    # Basic validation / sanitization of pieces
    if not isinstance(pieces, list):
        raise ValueError("pieces must be a list")
    # sanitize each piece (will raise if suspicious)
    try:
        safe_pieces = _sanitize_obj(pieces)
    except ValueError as e:
        raise RuntimeError(f"Invalid simulation input: {e}")

    input_data = {
        "pieces": safe_pieces,
        "boardBefore": int(board_before),
        "boardAfter": int(board_after),
    }

    raw = json.dumps(input_data)
    if len(raw.encode("utf-8")) > max_input_bytes:
        raise RuntimeError("Input too large")

    # Resolve node executable: allow env override, prefer `node`, then `nodejs`.
    node_exec = os.environ.get("NODE_EXECUTABLE", "node")
    node_path = shutil.which(node_exec) or shutil.which("nodejs")
    if not node_path:
        raise RuntimeError("node executable not found; install Node.js or set NODE_EXECUTABLE env var")

    # Resolve the headless script path. Prefer HEADLESS_SCRIPT env var, then
    # static/headless.mjs relative to this module, then a sibling headless.mjs.
    script_path = os.environ.get("HEADLESS_SCRIPT")
    if not script_path:
        base_dir = os.path.dirname(__file__)
        script_path = os.path.join(base_dir, "static", "headless.mjs")
        if not os.path.exists(script_path):
            alt = os.path.join(base_dir, "headless.mjs")
            if os.path.exists(alt):
                script_path = alt

    if not script_path or not os.path.exists(script_path):
        raise RuntimeError(f"headless script not found (looked at: {script_path})")

    # Use the current environment but ensure NODE_ENV is set for the child
    env = os.environ.copy()
    env["NODE_ENV"] = env.get("NODE_ENV", "production")
    print("running headless.mjs")

    proc = subprocess.run(
        [node_path, script_path],
        input=raw,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        env=env
    )
    print("finished running headless.mjs")
    
    

    if proc.returncode != 0:
        # include stderr for debugging, but avoid logging full user input in prod
        # TODO: reintroduce .strip() to the end of stderr for security (and remove prints)
        print(proc.stdout)
        print(proc.stderr)
        print("simulation failed")
        raise RuntimeError(f"JavaScript simulation failed: {proc.stderr}")

    # parse and sanitize returned JSON as well (optional but recommended)
    parsed = json.loads(proc.stdout)
    # Expect the returned structure; sanitize before using
    if not isinstance(parsed, dict):
        raise RuntimeError("Unexpected simulation output")

    # If the JS returns a `pieces` key, use it directly (legacy/explicit API).
    if "pieces" in parsed:
        parsed["pieces"] = _sanitize_obj(parsed["pieces"])
        return parsed

    # Some JS runner implementations (like headless.mjs) return `survivors`
    # (one entry per input piece) rather than `pieces`. Map survivors back to
    # a `pieces` list, preserving owner and other original metadata by index.
    if "survivors" in parsed:
        survivors = parsed["survivors"]
        if not isinstance(survivors, list):
            raise RuntimeError("Unexpected simulation output: survivors must be a list")

        new_pieces = []
        for i, s in enumerate(survivors):
            if not isinstance(s, dict):
                raise RuntimeError("Unexpected simulation output: survivor entry not an object")

            # Preserve owner (and any other original keys) by indexing into the
            # input pieces we sent to the JS runner (safe_pieces).
            owner = None
            orig = None
            if i < len(safe_pieces) and isinstance(safe_pieces[i], dict):
                orig = safe_pieces[i]
                owner = orig.get("owner")

            piece = {
                "owner": owner,
                "pieceid": s.get("pieceid"),
                "x": s.get("x"),
                "y": s.get("y"),
                "vx": s.get("vx"),
                "vy": s.get("vy"),
            }
            # carry through color if provided by JS or original
            color = s.get("color") if isinstance(s.get("color"), str) else None
            if not color and orig and isinstance(orig.get("color"), str):
                color = orig.get("color")
            if color:
                piece["color"] = color

            # sanitize each produced piece before adding
            new_pieces.append(_sanitize_obj(piece))

        return {"pieces": new_pieces, "steps": parsed.get("steps")}

    # Unknown shape
    raise RuntimeError("Unexpected simulation output: missing `pieces` or `survivors`")


def run_daily_game_updates():
    #TODO: REMOVE before using this for real, but this was the easiest spot to     
    return 1/0;

    print(f"Running daily game simulation at {datetime.now()}...")
    for game_id, game in GAMES.items():
        pieces = game["state"].get("pieces", [])
        if not pieces:
            continue
        try:
            new_state = run_js_simulation(pieces)
            game["state"]["pieces"] = new_state["pieces"]
            game["last_updated"] = datetime.now().isoformat()
            print(f"✅ Updated game {game_id}")
        except Exception as e:
            print(f"❌ Failed to update {game_id}: {e}")
