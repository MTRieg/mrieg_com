# game_simulation.py
import json
import subprocess
from datetime import datetime
import zoneinfo
import random
import math
import shutil
import os
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Type-ignore import to avoid circular import at runtime; used only for typing
try:
    from stores.game_store import GameStore  # type: ignore
    from stores import GameNotFound, TurnMismatch, InvalidState, SimulationError, UnexpectedResult
except Exception:  # pragma: no cover - typing fallback
    GameStore = Any  # type: ignore
    GameNotFound = Exception
    TurnMismatch = Exception
    InvalidState = Exception
    SimulationError = Exception
    UnexpectedResult = Exception

DEFAULT_BOARD_SIZE = 800
DEFAULT_BOARD_SHRINK = 50
DEFAULT_RADIUS = 30
DEFAULT_MASS = 1


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
        new_state = run_js_simulation(
            pieces_before_filtered,
            board_before=board_size,
            board_after=board_size - board_shrink,
        )
    except Exception as e:
        logger.exception("simulation run failed for game: %s", game.get("id"))
        raise RuntimeError("simulation failed") from e
        

    game["state"]["pieces"] = new_state.get("pieces", []) + pieces_before_out
    game["state"]["turn_number"] += 1
    try:
        tz = zoneinfo.ZoneInfo(os.environ.get("GAME_TIMEZONE", "America/Toronto"))
    except Exception:
        tz = zoneinfo.ZoneInfo("UTC")
    game["state"]["last_turn_time"] = datetime.now(tz)
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


def run_js_simulation(pieces, board_before=DEFAULT_BOARD_SIZE, board_after=DEFAULT_BOARD_SIZE - DEFAULT_BOARD_SHRINK, *,
                      max_input_bytes=200_000, timeout_s=10):
    logger.debug("running simulation: board %s -> %s (pieces=%d)", board_before, board_after, len(pieces) if isinstance(pieces, list) else 0)
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
    node_exec = os.environ.get("NODE_EXECUTABLE") or "node"
    node_path = shutil.which(node_exec) or shutil.which("nodejs")
    if not node_path:
        logger.error("node executable not found; NODE_EXECUTABLE=%s", node_exec)
        raise RuntimeError("node executable not found; install Node.js or set NODE_EXECUTABLE env var")

    # Resolve the headless script path. Prefer HEADLESS_SCRIPT env var, then
    # static/headless.mjs relative to this module, then a sibling headless.mjs.
    script_path = os.environ.get("HEADLESS_SCRIPT")
    if not script_path:
        base_dir = os.path.dirname(__file__)
        candidates = [
            os.path.join(base_dir, "headless.mjs"),
            os.path.join(base_dir, "static", "headless.mjs"),
            os.path.join(os.getcwd(), "static", "headless.mjs"),
            os.path.join(os.path.dirname(base_dir), "static", "headless.mjs"),
        ]
        for c in candidates:
            if os.path.exists(c):
                script_path = c
                break

    if not script_path or not os.path.exists(script_path):
        logger.error("headless script not found; checked HEADLESS_SCRIPT=%s and candidates", script_path)
        raise RuntimeError(f"headless script not found (looked at: {script_path})")

    # Use the current environment but ensure NODE_ENV is set for the child
    env = os.environ.copy()
    env["NODE_ENV"] = env.get("NODE_ENV", "production")
    logger.debug("running headless script: %s", script_path)

    proc = subprocess.run(
        [node_path, script_path],
        input=raw,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        env=env
    )
    logger.debug("finished running headless script (returncode=%s)", proc.returncode)
    
    

    if proc.returncode != 0:
        # include stderr for debugging
        logger.error("simulation failed: stdout=%s stderr=%s", proc.stdout, proc.stderr)
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


# -----------------------------
# Integration helpers (async)
# -----------------------------


async def simulate_and_replace(game_store: "GameStore", game_id: str, owner: str) -> Dict[str, Any]:
    """Run the JS simulation against current pieces and replace pieces.

    This function will:
    - load current pieces and settings
    - run `run_js_simulation` to compute new pieces
    - call `game_store.replace_pieces` to atomically store new pieces

    Note: this helper does NOT increment turn counters or clear submissions; that
    should be handled by `game_store.advance_turn_if_ready` or other higher-level
    orchestration to preserve invariants.
    
    Args:
        game_store: GameStore instance
        game_id: ID of the game
        owner: Owner player ID (for logging)
    
    Returns:
        dict with status, updated_count, turn_number
        
    Raises:
        GameNotFound: if game does not exist
        SimulationError: if physics simulation fails
        Exception: if pieces replacement fails
    """
    try:
        settings = await game_store.get_game_settings(game_id)
        pieces = await game_store.get_pieces(game_id)

        board_before = int(settings.get("board_size", DEFAULT_BOARD_SIZE))
        board_shrink = int(settings.get("board_shrink", DEFAULT_BOARD_SHRINK))
        board_after = board_before - board_shrink

        logger.info("Running simulation for game %s: pieces=%d", game_id, len(pieces))
        try:
            sim = run_js_simulation(pieces, board_before=board_before, board_after=board_after)
        except RuntimeError as e:
            logger.error(f"Simulation failed for game {game_id}: {e}")
            raise SimulationError(f"Physics simulation failed: {str(e)}")

        new_pieces = sim.get("pieces", [])
        await game_store.replace_pieces(game_id, new_pieces)

        # Optionally return summary info
        state = await game_store.get_game_state(game_id)
        return {
            "status": "success",
            "updated_count": len(new_pieces),
            "turn_number": state.get("turn_number"),
        }

    except GameNotFound:
        logger.warning(f"Simulation requested for non-existent game: {game_id}")
        raise
    except SimulationError:
        # Already logged and wrapped
        raise
    except Exception:
        logger.exception("Failed simulation for game %s", game_id)
        raise


async def simulate_turn_if_ready(game_store: "GameStore", game_id: str, owner: str) -> Dict[str, Any]:
    """High-level helper: advance the turn if ready, then run simulation.

    Workflow:
    - call `advance_turn_if_ready`; if it returns False, return `{'status':'not_ready'}`
    - if True, call `simulate_and_replace` to run the JS and persist pieces
    
    Args:
        game_store: GameStore instance
        game_id: ID of the game
        owner: Owner player ID (for logging/authorization)
    
    Returns:
        dict with status and optionally updated_count, turn_number
        
    Raises:
        GameNotFound: if game does not exist
        TurnMismatch: if turn_number does not match
        InvalidState: if game state is invalid
        SimulationError: if physics simulation fails
        UnexpectedResult: if unexpected error occurs
    """
    try:
        # Note: advance_turn_if_ready now requires turn_number parameter
        # This function signature may need updating to accept turn_number
        advanced = await game_store.advance_turn_if_ready(game_id, owner)
        if not advanced:
            return {"status": "not_ready"}

        # When the turn was advanced, run the simulation and apply results
        return await simulate_and_replace(game_store, game_id, owner)
    except (GameNotFound, TurnMismatch, InvalidState, SimulationError, UnexpectedResult):
        # Expected errors - propagate to caller
        raise
    except Exception as e:
        logger.error(f"simulate_turn_if_ready failed for game {game_id}: {e}", exc_info=True)
        raise


__all__ = [
    "advance_simulation",
    "run_js_simulation",
    "simulate_and_replace",
    "simulate_turn_if_ready",
    "DEFAULT_BOARD_SIZE",
    "DEFAULT_BOARD_SHRINK",
    "DEFAULT_RADIUS",
    "DEFAULT_MASS",
]


