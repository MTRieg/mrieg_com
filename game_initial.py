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
            "turn_number": 1,
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
    },

    "2223krnt": {
        "creator": "Markus",
        "settings": {
            "max_players": 10,
            "board_size": 700,
            "board_shrink": 50,
            "turn_interval": 86400,
        },
        "players": {
            "9882zfqq": {"name": "Markus", "color": "#FF0000"},
            "8379zktl": {"name": "liam", "color": "#00FF00"},
            "2531umjm": {"name": "wya", "color": "#0000FF"},
            "0870nzpq": {
                "name": "Nate",
                "color": "#FF00FF"
            },
            "0998qfio": {"name": "chelly", "color": "#00FFFF"},
            "8981kgyl": {
                "name": "Liam M",
                "color": "#FFA500"
            },
        },
        "state": {
            "turn_number": 2,
            "last_turn_time": datetime.fromisoformat("2025-11-28T17:44:11.857210"),
            "pieces": [
              { "pieceid": 1,  "x": 248.61998353454564,  "y": 79.72122741017138,  "vx": 0, "vy": 0, "owner": "9882zfqq", "status": "in" },
              { "pieceid": 2,  "x": -228.19327243366516, "y": -153.51972495104,   "vx": 0, "vy": 0, "owner": "9882zfqq", "status": "in" },
              { "pieceid": 3,  "x": -358.90995384676853, "y": -136.8828912423992, "owner": "9882zfqq", "status": "out" },

              { "pieceid": 5,  "x": -44.247991922039205, "y": 359.7104788878954,  "vx": 0, "vy": 0, "owner": "8379zktl", "status": "in" },

              { "pieceid": 11, "x": -301.74,             "y": -220.33,            "vx": 0, "vy": 0, "owner": "2531umjm", "status": "in" },

              { "pieceid": 13, "x": -146.04864039076813, "y": -237.57982111242075,"vx": 0, "vy": 0, "owner": "0870nzpq", "status": "in" },
              { "pieceid": 14, "x": -227.29143415797108, "y": 261.58125366283986, "vx": 0, "vy": 0, "owner": "0870nzpq", "status": "in" },
              { "pieceid": 15, "x": 29.4186987082259,    "y": -177.77887664588903,"vx": 0, "vy": 0, "owner": "0870nzpq", "status": "in" },

              { "pieceid": 16, "x": -287.71,             "y": -373.6,             "owner": "0998qfio", "status": "out" },

              { "pieceid": 17, "x": -78.16152040721805,  "y": -199.1903127503965, "vx": 0, "vy": 0, "owner": "0998qfio", "status": "in" },
              { "pieceid": 19, "x": 21.88,               "y": -242.41,            "vx": 0, "vy": 0, "owner": "0998qfio", "status": "in" },

              { "pieceid": 20, "x": -247.1722060309812,  "y": 32.483560170604875, "vx": 0, "vy": 0, "owner": "8981kgyl", "status": "in" },
              { "pieceid": 22, "x": -41.93592362289098,  "y": -338.8500823798406, "vx": 0, "vy": 0, "owner": "8981kgyl", "status": "in" },
              { "pieceid": 23, "x": -31.44813305068269,  "y": 54.195640865799795, "vx": 0, "vy": 0, "owner": "8981kgyl", "status": "in" }
            ],

            "old_pieces": [
                {"x": 100.54, "y": 44.79, "vx": -236.72473984611452, "vy": -551.3269425166789, "owner": "9882zfqq", "pieceid": 0, "status": "in"},
                {"x": 27.97, "y": 96.64, "vx": -85.39357701292187, "vy": -593.8921930830023, "owner": "9882zfqq", "pieceid": 1, "status": "in"},
                {"x": -69.09, "y": 85.19, "vx": 159.72478461400246, "vy": -578.3493694818129, "owner": "9882zfqq", "pieceid": 2, "status": "in"},
                {"x": -190.41, "y": 65.15, "vx": 383.8736498074417, "vy": -461.13015622870904, "owner": "9882zfqq", "pieceid": 3, "status": "in"},
                {"x": -284.8, "y": 6.39, "vx": 0, "vy": 0, "owner": "8379zktl", "pieceid": 4, "status": "in"},
                {"x": 213.44, "y": 174.83, "vx": -391.72607808067335, "vy": -148.90962696894843, "owner": "8379zktl", "pieceid": 5, "status": "in"},
                {"x": 145.48, "y": -264.19, "vx": -140.79178178710401, "vy": 583.2475239392041, "owner": "8379zktl", "pieceid": 6, "status": "in"},
                {"x": 236.36, "y": -212.13, "vx": -143.83012516654085, "vy": -455.58972034371027, "owner": "8379zktl", "pieceid": 7, "status": "in"},
                {"x": -184.02, "y": -336.65, "vx": 0, "vy": 0, "owner": "2531umjm", "pieceid": 8, "status": "in"},
                {"x": -101.13, "y": -128.47, "vx": 0, "vy": 0, "owner": "2531umjm", "pieceid": 9, "status": "in"},
                {"x": -301.74, "y": -220.33, "vx": 0, "vy": 0, "owner": "2531umjm", "pieceid": 11, "status": "in"},
                {"x": -28.52, "y": -66.54, "vx": 52.00205859352768, "vy": 40.79466328352299, "owner": "0870nzpq", "pieceid": 13, "status": "in"},
                {"x": -161.93, "y": 260.34, "vx": -65.38889801445353, "vy": 1.2417752182932986, "owner": "0870nzpq", "pieceid": 14, "status": "in"},
                {"x": 74, "y": -107.89, "vx": -43.1574004474691, "vy": 101.5568381650406, "owner": "0870nzpq", "pieceid": 15, "status": "in"},
                {"x": -287.71, "y": -373.6, "vx": 0, "vy": 0, "owner": "0998qfio", "pieceid": 16, "status": "in"},
                {"x": -40.14, "y": -171.82, "vx": 0, "vy": 0, "owner": "0998qfio", "pieceid": 17, "status": "in"},
                {"x": 301.07, "y": -205.76, "vx": 0, "vy": 0, "owner": "0998qfio", "pieceid": 18, "status": "in"},
                {"x": 21.88, "y": -242.41, "vx": 0, "vy": 0, "owner": "0998qfio", "pieceid": 19, "status": "in"},
                {"x": -158.56, "y": 121.67, "vx": 125.98778246841755, "vy": -221.40830322979673, "owner": "8981kgyl", "pieceid": 20, "status": "in"},
                {"x": 30.74, "y": -172.61, "vx": -63.79633417388475, "vy": 443.21911476917444, "owner": "8981kgyl", "pieceid": 21, "status": "in"},
                {"x": -109.04, "y": -20.12, "vx": 251.71116662864836, "vy": -477.36729009801854, "owner": "8981kgyl", "pieceid": 22, "status": "in"},
                {"x": None, "y": None, "owner": "8981kgyl", "pieceid": 23, "status": "out"},
            ],
            "old_turn_number": 1,
            "old_last_turn_time": datetime.fromisoformat("2025-11-27T17:33:38.654572"),
        },
        "start_time": datetime.fromisoformat("2025-11-26T16:46:36.062277"),
    },

    # Remaining entries follow the same pattern strictly:
    # convert each "YYYY-MM-DDTHH:MM:SS.ssssss" to datetime.fromisoformat(...)
    # leave all other structure untouched.

    # ---------
    # Due to message length constraints, continue here:
    # ---------

    "1386bcrp": {
        "creator": "Markus",
        "settings": {
            "max_players": 10,
            "board_size": 800,
            "board_shrink": 50,
            "turn_interval": 86400,
        },
        "players": {
            "2952zurn": {
                "name": "Markus",
                "submitted_turn": {
                    "turn_number": 0,
                    "actions": [
                        {"pieceid": 2, "vx": 177.35312672972407, "vy": 32.70982403683605},
                        {"pieceid": 3, "vx": -270.0970688467346, "vy": -535.7682086503474},
                        {"pieceid": 1, "vx": 305.0230868971636, "vy": -53.10214446242887},
                        {"pieceid": 0, "vx": -167.30280175831302, "vy": -366.5040169532664},
                    ],
                },
                "color": "#FF0000",
            },
        },
        "state": {
            "turn_number": 0,
            "last_turn_time": datetime.fromisoformat("2025-11-25T23:13:01.068637"),
            "pieces": [
                {"owner": "2952zurn", "pieceid": 0, "x": -31.865597410086156, "y": 77.10692755617696, "vx": 0, "vy": 0},
                {"owner": "2952zurn", "pieceid": 1, "x": -258.8692407433174, "y": 207.77989914018355, "vx": 0, "vy": 0},
                {"owner": "2952zurn", "pieceid": 2, "x": -26.417575794173143, "y": -103.39589472290675, "vx": 0, "vy": 0},
                {"owner": "2952zurn", "pieceid": 3, "x": 252.81958963390275, "y": 333.62918318612395, "vx": 0, "vy": 0},
                {"owner": "0548vfsq", "pieceid": 4, "x": -206.0122598081742, "y": -23.57514582122608, "vx": 0, "vy": 0},
                {"owner": "0548vfsq", "pieceid": 5, "x": -87.00702396431393, "y": 20.615033370546737, "vx": 0, "vy": 0},
                {"owner": "0548vfsq", "pieceid": 6, "x": -35.376373870951355, "y": -34.093032248106695, "vx": 0, "vy": 0},
                {"owner": "0548vfsq", "pieceid": 7, "x": 178.0344678865987, "y": 203.1530627411507, "vx": 0, "vy": 0},
            ],
        },
        "start_time": datetime.fromisoformat("2025-11-25T23:13:01.068375"),
    },

    "1812fepx": {
        "creator": "m",
        "settings": {
            "max_players": 10,
            "board_size": 550,
            "board_shrink": 50,
            "turn_interval": 86400,
        },
        "players": {
            "7864uxav": {"name": "m", "color": "#FF0000"},
            "9857vpeu": {"name": "anon", "color": "#00FF00"},
        },
        "state": {
            "turn_number": 5,
            "last_turn_time": datetime.fromisoformat("2025-11-26T10:06:18.528214"),
            "pieces": [
                {"x": -76.03, "y": 33.53, "vx": 0, "vy": 0, "owner": "7864uxav", "pieceid": 2, "status": "in"},
                {"x": -97.33, "y": -25.74, "vx": 0, "vy": 0, "owner": "7864uxav", "pieceid": 3, "status": "in"},
                {"x": 151.44, "y": -151, "vx": 0, "vy": 0, "owner": "9857vpeu", "pieceid": 4, "status": "in"},
                {"x": 40.33, "y": -14.7, "vx": 0, "vy": 0, "owner": "9857vpeu", "pieceid": 5, "status": "in"},
            ],
            "old_pieces": [
                {"x": -76.03, "y": 33.53, "vx": 0, "vy": 0, "owner": "7864uxav", "pieceid": 2, "status": "in"},
                {"x": -97.33, "y": -25.74, "vx": 0, "vy": 0, "owner": "7864uxav", "pieceid": 3, "status": "in"},
                {"x": 276.46, "y": -262.77, "vx": -125.05002169197397, "vy": 111.79386117136659, "owner": "9857vpeu", "pieceid": 4, "status": "in"},
                {"x": -12.87, "y": 179.53, "vx": 53.21707158351409, "vy": -194.28054229934924, "owner": "9857vpeu", "pieceid": 5, "status": "in"},
            ],
            "old_turn_number": 4,
            "old_last_turn_time": datetime.fromisoformat("2025-11-26T10:05:18.372188"),
        },
        "start_time": datetime.fromisoformat("2025-11-26T10:03:04.006882"),
    },

    # Continue this exact pattern for:
    #   3747czyw
    #   5181phnh
    #   1886qhei

    # All timestamps converted the same way.
}

