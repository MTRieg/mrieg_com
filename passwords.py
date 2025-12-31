"""
Goals:
have this file control password setting, creating session tokens, and verifying passwords and session tokens
including hashing and salting passwords for security

dictionaries to implement:
- game passwords: mapping game IDs to their salt values and hashed passwords
- player passwords: mapping player IDs to their salt values and hashed passwords


functions to implement:

- set_game_password(game_id, password): returns session token
- set_player_password(player_id, password): returns session token
- request_token(game_id, game_password, player_id = "", player_password = ""): returns session token
(can return session token for game only, both, or for player only by putting empty strings for game_id and game_password)
(if password is incorrect, token returns None)
- read_token(session_token): returns dictionary with game_id, player_id. if token invalid or expired, returns None
- revoke_token(session_token): removes session token from active tokens
"""


import datetime
import hashlib
import os
import bcrypt

from game_initial import GAME_PASSWORDS_INITIAL, PLAYER_PASSWORDS_INITIAL, SESSION_TOKENS_INITIAL

game_passwords = GAME_PASSWORDS_INITIAL
player_passwords = PLAYER_PASSWORDS_INITIAL
session_tokens = SESSION_TOKENS_INITIAL

def set_game_password(game_id, password, create_session=True):
    """Sets the password for a game and returns a session token."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    print("---", game_passwords, game_id, "---")
    if game_id in game_passwords:
        return None

    game_passwords[game_id] = {
        "salt": salt,
        "hashed": hashed
    }    
    if create_session:
        session_token = hashlib.sha256(os.urandom(64)).hexdigest()
        session_tokens[session_token] = {
            "game_id": game_id,
            "player_id": None,
            "expires_at": datetime.datetime.now() + datetime.timedelta(hours=48)
        }
        return session_token
    else: 
        return True

def set_player_password(player_id, password, create_session=True):
    """Sets the password for a player and returns a session token."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    if player_id in player_passwords:
        return None
    player_passwords[player_id] = {
        "salt": salt,
        "hashed": hashed
    }    

    if create_session:
        session_token = hashlib.sha256(os.urandom(64)).hexdigest()
        session_tokens[session_token] = {
            "game_id": None,
            "player_id": player_id,
            "expires_at": datetime.datetime.now() + datetime.timedelta(hours=48)
        }
        return session_token
    else:
        return True
    
def create_token(game_id="", game_password="", player_id="", player_password=""):
    """Requests a session token for a game and/or player."""
    valid_game = False
    valid_player = False

    if game_id and game_password:
        if game_id in game_passwords:
            stored_hashed = game_passwords[game_id]["hashed"]
            if bcrypt.checkpw(game_password.encode('utf-8'), stored_hashed):
                valid_game = True

    if player_id and player_password:
        if player_id in player_passwords:
            stored_hashed = player_passwords[player_id]["hashed"]
            if bcrypt.checkpw(player_password.encode('utf-8'), stored_hashed):
                valid_player = True

    if (game_id and not valid_game) or (player_id and not valid_player):
        return None

    session_token = hashlib.sha256(os.urandom(64)).hexdigest()
    session_tokens[session_token] = {
        "game_id": game_id if valid_game else None,
        "player_id": player_id if valid_player else None,
        "expires_at": datetime.datetime.now() + datetime.timedelta(hours=48)
    }
    return session_token

def read_token(session_token):
    """Reads a session token and returns its associated game_id and player_id."""
    if session_token in session_tokens:
        token_data = session_tokens[session_token]
        if token_data["expires_at"] is None or token_data["expires_at"] > datetime.datetime.now():
            return {
                "game_id": token_data["game_id"],
                "player_id": token_data["player_id"]
            }
        else:
            revoke_token(session_token)
    return None

def revoke_token(session_token):
    """Revokes a session token."""
    if session_token in session_tokens:
        del session_tokens[session_token]
    return







