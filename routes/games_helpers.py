"""
Game business logic helpers.

These functions encapsulate game operations and can be called from:
- HTTP routes (routes/games.py)
- Celery tasks (workers/tasks.py)
- Other internal services, if such services are added in the future

They operate on domain objects and store instances, not HTTP requests.
"""

from typing import Any, Dict
from stores import (
	GameStore, 
	GameFull,
	TurnMismatch,
    PlayerAlreadyJoinedGame, 
    CreatorOnlyAction,
)
import random
import math
from datetime import datetime, timezone



def censor_game_state(game_data: dict) -> dict:
    """Remove 'locked_by' from state and zero-out piece velocities in-place."""
    if not isinstance(game_data, dict):
        return game_data

    pieces = game_data.get('pieces')
    if isinstance(pieces, list):
        for p in pieces:
            if isinstance(p, dict):
                if 'vx' in p:
                    p['vx'] = 0.0
                if 'vy' in p:
                    p['vy'] = 0.0

    return game_data


async def join_game(
    store: GameStore,
    game_id: str,
    player_id: str,
) -> Dict[str, Any]:
    """
    Add a player to an existing game.
    
    Args:
        store: GameStore instance
        game_id: ID of the game to join
        player_id: ID of the player joining
    
    Returns:
        dict with game_id and player_id
    
    Raises:
        GameNotFound: if game does not exist
        GameFull: if game has reached max_players
        PlayerNotFound: if player does not exist
        PlayerAlreadyJoinedGame: if player is already in the game
    """
    # Get the game to validate state
    game = await store.get_game(game_id)
    
    # Check if player already in game
    if player_id in game.get("players", {}):
        raise PlayerAlreadyJoinedGame(f"Player {player_id} already in game {game_id}")
    
    # Check if game is full
    max_players = game.get("settings", {}).get("max_players", 4)
    if len(game.get("players", {})) >= max_players:
        raise GameFull(f"Game {game_id} is full")
    
    # Add player to game using the store method
    # The database triggers will automatically set creator if this is the first player
    await store.add_player_to_game(
        game_id,
        player_id,
        name=player_id,
        color=None,
    )
    
    return {
        "game_id": game_id,
        "player_id": player_id,
        "message": "Player added to game",
    }


async def leave_game(
    store: GameStore,
    game_id: str,
    player_id: str,
) -> Dict[str, Any]:
    """
    Remove a player from a game.
    
    Args:
        store: GameStore instance
        game_id: ID of the game
        player_id: ID of the player leaving
    
    Returns:
        dict with game_id and player_id
    
    Raises:
        GameNotFound: if game does not exist
        PlayerNotFound: if player is not in the game
    """
    # Remove player from game using store method
    # Database triggers will automatically handle creator reassignment
    await store.leave_game(game_id, player_id)
    
    return {
        "game_id": game_id,
        "player_id": player_id,
        "message": "Player removed from game"
    }


async def delete_game(
    store: GameStore,
    game_id: str,
    owner_id: str,
) -> Dict[str, Any]:
    """
    Delete a game (admin/owner operation).
    
    Args:
        store: GameStore instance
        game_id: ID of the game to delete
        owner_id: ID of the requesting player (for authorization check)
    
    Returns:
        dict with status and game_id
    
    Raises:
        GameNotFound: if game does not exist
        CreatorOnlyAction: if owner_id is not the game creator
    """
    # Get the game
    game = await store.get_game(game_id)
    
    # Check authorization: only creator can delete
    if owner_id != game.get("creator"):
        raise CreatorOnlyAction(f"Only game creator can delete the game")
    
    # Delete the game (store manages its own locking internally)
    await store.delete_game(game_id)
    
    return {
        "game_id": game_id,
        "status": "deleted",
        "message": "Game deleted",
    }


async def submit_turn(
    store: GameStore,
    game_id: str,
    player_id: str,
    turn_number: int,
    actions: list[Dict[str, Any]],
    owner_id: str = None,  # Deprecated, but kept for signature compatibility
) -> Dict[str, Any]:
    """
    Submit a turn for a player in a game.
    
    Args:
        store: GameStore instance
        game_id: ID of the game
        player_id: ID of the player submitting
        turn_number: Current turn number
        actions: List of action objects to execute
        owner_id: Deprecated, no longer used
    
    Returns:
        dict with game_id, player_id, turn_number
    
    Raises:
        GameNotFound: if game does not exist
        PlayerNotFound: if player is not in the game
        TurnMismatch: if provided turn_number does not match server's current turn
    """
    # Submit turn using the atomic store method
    await store.submit_turn(
        game_id=game_id,
        player_id=player_id,
        turn_number=turn_number,
        actions=actions,
    )
    
    # Check if all players have now submitted their turns
    all_submitted = await store.all_players_submitted(game_id)
    
    return {
        "game_id": game_id,
        "player_id": player_id,
        "turn_number": turn_number,
        "all_submitted": all_submitted,
    }

async def start_game(
    store: GameStore,
    game_id: str,
    owner_id: str,
) -> Dict[str, Any]:
    """
    Initialize game state for play (create initial pieces, set turn to 0, etc).
    
    Args:
        store: GameStore instance
        game_id: ID of the game
        owner_id: ID of the requesting player (for authorization)
    
    Returns:
        dict with game_id, status, turn_number
    
    Raises:
        GameNotFound: if game does not exist
        TurnMismatch: if game has already been started (turn_number != 0)
        InvalidState: if game has invalid state
        CreatorOnlyAction: if owner_id is not the game creator
    """
    # Get the game
    game = await store.get_game(game_id)

    # Check authorization: only creator or system can start
    if owner_id not in [game.get("creator"), "system"]:
        raise CreatorOnlyAction(f"Only game creator can start the game")

    # Check if already started
    if game.get("pieces"):
        raise TurnMismatch(f"Game has already been started")

    # Generate player colors
    player_ids = list(game["players"].keys())
    colors = initialize_colors(player_ids)

    # Generate initial pieces
    pieces = initialize_pieces(
        player_ids,
        game["settings"]["board_size"],
        pieces_per_player=4  # or make this configurable
    )
    
    last_turn_time = datetime.now(timezone.utc)

    # Call the store's start_game to persist all initial state
    await store.start_game(
        game_id=game_id,
        pieces=pieces,
        colors=colors,
        last_turn_time=last_turn_time,
    )

    return {
        "game_id": game_id,
        "status": "started",
        "message": "Game started",
    }



async def apply_moves_and_run_game(
    store: GameStore,
    game_id: str,
    turn_number: int = None,
) -> Dict[str, Any]:
    """
    Combined operation: apply submitted moves + run simulation + advance turn atomically.
    
    This is the primary way to drive the game forward. It atomically:
    - collects all player submissions
    - applies moves to piece velocities
    - runs the physics simulation
    - clears submissions
    - increments the turn counter
    
    Args:
        store: GameStore instance
        game_id: ID of the game
        turn_number: Current turn number
    
    Returns:
        dict with game_id, turn_number, advanced (bool)
    
    Raises:
        GameNotFound: if game does not exist
        InvalidState: if game state is invalid
        TurnMismatch: if turn_number does not match server's current turn
        SimulationError: if physics simulation fails
        UnexpectedResult: if unexpected error occurs during turn advancement
    """
    advanced = await store.advance_turn_if_ready(game_id, turn_number=turn_number)
    
    if not advanced:
        return {
            "game_id": game_id,
            "advanced": False,
            "message": "Turn could not be advanced",
        }
    
    # Get updated state after turn advancement
    state = await store.get_game_state(game_id)
    
    return {
        "game_id": game_id,
        "turn_number": state.get("turn_number", 0),
        "advanced": True,
        "status": "completed",
    }



def initialize_colors(player_ids):
    """Return a dict mapping player_id to a distinct color."""
    base_colors = [
        "#FF0000", "#00FF00", "#0000FF", "#FF00FF", "#00FFFF",
        "#FFA500", "#800080", "#008000", "#FFC0CB", "#A52A2A", "#808000",
        "#000080", "#800000", "#008080", "#C0C0C0", "#FFD700", "#DC143C",
        "#4682B4", "#DA70D6", "#ADFF2F", "#40E0D0", "#FA8072", "#7FFF00",
        "#1E90FF", "#BA55D3", "#FF8C00", "#B0C4DE", "#2E8B57", "#F08080",
        "#00CED1", "#FF1493", "#ADFF2F", "#FF4500", "#9ACD32", "#708090",
        "#20B2AA", "#CD5C5C", "#F0E68C", "#9932CC", "#8FBC8F", "#E9967A",
        "#B22222", "#5F9EA0", "#66CDAA", "#BC8F8F", "#556B2F", "#D2691E",
        "#483D8B", "#FF6347", "#6495ED", "#E6E6FA", "#BDB76B", "#A9A9A9"
    ]
    return {pid: base_colors[i % len(base_colors)] for i, pid in enumerate(player_ids)}

# --- Helper: initialize starting positions ---


def initialize_pieces(player_ids, board_size, pieces_per_player=4):
    """Return a list of initial pieces, turn_number, and last_turn_time."""
    import os
    import zoneinfo
    from datetime import datetime
    pieces = []
    piece_radius = 30
    edge_buffer = 50

    def is_valid_position(x, y):
        if x < edge_buffer - board_size or x > board_size - edge_buffer:
            return False
        if y < edge_buffer - board_size or y > board_size - edge_buffer:
            return False
        for p in pieces:
            dx = p["x"] - x
            dy = p["y"] - y
            if math.hypot(dx, dy) < 2 * piece_radius + 5:
                return False
        return True

    for i, player in enumerate(player_ids):
        for j in range(pieces_per_player):
            for _ in range(1000):
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
            # else: could not place piece for this player
    return pieces





