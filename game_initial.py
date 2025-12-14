#game_initial.py
from datetime import datetime

GAMES_INITIAL = {
    "db0cfa34": {
        "creator": "anon",
        "settings": {
            "max_players": 10,
            "board_size": 800,
            "board_shrink": 50,
            "turn_interval": 86400,
        },
        "players": {
            "55eb1155": {
                "name": "anon",
                "submitted_turn": None,
                "color": "#FF0000",
            },
            "adbc9e96": {
                "name": "mark",
                "submitted_turn": {
                    "turn_number": 1,
                    "actions": [
                        {"pieceid": 4, "vx": 284.37012469069344, "vy": -46.639734398471745},
                        {"pieceid": 6, "vx": 539.0395524506522, "vy": -62.37063131222186},
                        {"pieceid": 7, "vx": 602.2985881344641, "vy": -259.09700179458315},
                        {"pieceid": 5, "vx": -395.28181041422033, "vy": -249.0655915290617},
                    ],
                },
                "color": "#00FF00",
            },
        },
        "state": {
            "turn_number": 3,
            "last_turn_time": datetime.fromisoformat("2025-10-29T22:34:22.270425"),
            "pieces": [
                {"owner": "55eb1155", "pieceid": 0, "x": 107.09103974961678, "y": 342.32851910531184, "vx": 0, "vy": 0},
                {"owner": "55eb1155", "pieceid": 1, "x": 68.94682717001216, "y": -46.023124588627645, "vx": 0, "vy": 0},
                {"owner": "55eb1155", "pieceid": 2, "x": -192.9158714026313, "y": 29.52752136219311, "vx": 0, "vy": 0},
                {"owner": "55eb1155", "pieceid": 3, "x": -238.2281308217178, "y": 318.1080708580444, "vx": 0, "vy": 0},
                {"owner": "adbc9e96", "pieceid": 4, "x": -300.2733472600038, "y": -3.8209714309518916, "vx": 0, "vy": 0},
                {"owner": "adbc9e96", "pieceid": 5, "x": 284.5417979557438, "y": 249.62218540945918, "vx": 0, "vy": 0},
                {"owner": "adbc9e96", "pieceid": 6, "x": -306.1432018177364, "y": 85.23175398712351, "vx": 0, "vy": 0},
                {"owner": "adbc9e96", "pieceid": 7, "x": -369.23835257720066, "y": 263.07583702851235, "vx": 0, "vy": 0},
            ],
        },
        "start_time": datetime.fromisoformat("2025-10-29T22:34:22.270220"),
    }
}

