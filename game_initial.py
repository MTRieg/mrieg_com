import json
from datetime import datetime
from pathlib import Path
import bcrypt
def object_parser(filename):
    """Return a parser function that knows which file it's parsing."""
    def parser(dct):
        """Convert ISO format datetime strings to datetime objects in specific fields."""
        if filename == "games.json":
            if "start_time" in dct and isinstance(dct["start_time"], str):
                try:
                    dct["start_time"] = datetime.fromisoformat(dct["start_time"])
                except (ValueError, AttributeError):
                    pass
            
            if "state" in dct and isinstance(dct["state"], dict):
                if "last_turn_time" in dct["state"] and isinstance(dct["state"]["last_turn_time"], str):
                    try:
                        dct["state"]["last_turn_time"] = datetime.fromisoformat(dct["state"]["last_turn_time"])
                    except (ValueError, AttributeError):
                        pass
                
                if "old_last_turn_time" in dct["state"] and isinstance(dct["state"]["old_last_turn_time"], str):
                    try:
                        dct["state"]["old_last_turn_time"] = datetime.fromisoformat(dct["state"]["old_last_turn_time"])
                    except (ValueError, AttributeError):
                        pass
        
        elif filename == "session_tokens.json":
            if "expires_at" in dct and isinstance(dct["expires_at"], str):
                try:
                    dct["expires_at"] = datetime.fromisoformat(dct["expires_at"])
                except (ValueError, AttributeError):
                    pass
        
        elif filename == "players.json":
            if "date_created" in dct and isinstance(dct["date_created"], str):
                try:
                    dct["date_created"] = datetime.fromisoformat(dct["date_created"])
                except (ValueError, AttributeError):
                    pass
        
        elif filename in ["game_passwords.json", "player_passwords.json"]:
            # Convert bcrypt byte strings back to bytes
            if "salt" in dct and isinstance(dct["salt"], str):
                try:
                    dct["salt"] = eval(dct["salt"])
                except:
                    pass
            
            if "hashed" in dct and isinstance(dct["hashed"], str):
                try:
                    dct["hashed"] = eval(dct["hashed"])
                except:
                    pass
        
        return dct
    return parser


def load_from_file(filename, default):
    """Load data from JSON file, return default if file doesn't exist."""
    try:
        if Path(filename).exists():
            with open(filename, "r") as f:
                return json.load(f, object_hook=object_parser(filename))
    except (json.JSONDecodeError, IOError):
        pass
    return default

GAMES_INITIAL = load_from_file("games.json", dict())
PLAYERS_INITIAL = load_from_file("players.json", dict())
GAME_PASSWORDS_INITIAL = load_from_file("game_passwords.json", dict())
PLAYER_PASSWORDS_INITIAL = load_from_file("player_passwords.json", dict())
SESSION_TOKENS_INITIAL = load_from_file("session_tokens.json", dict())