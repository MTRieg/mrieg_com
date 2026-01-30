# Knockout Game Server

A real-time multiplayer game server built with FastAPI, WebSockets, and physics simulation via Node.js. Players control pieces on a grid, submit moves each turn, and the server runs physics simulations to determine outcomes.

## Architecture

**Services:**
- **FastAPI (Uvicorn)**: HTTP/WebSocket API on port 8000
- **Celery Worker**: Background task processing for turn advancement and game management
- **Redis**: Message broker and result backend for Celery
- **SQLite**: Game state and player data persistence

**Key Components:**
- `routes/`: HTTP endpoints for game management, authentication, turn submission
- `stores/`: Database abstraction layer with atomic locking for concurrent operations
- `services/game_simulation.py`: Physics engine wrapper calling Node.js headless simulation
- `static/`: Frontend (HTML/JS) for game UI and lobby
- `workers/`: Celery tasks for scheduled turn advancement

## Prerequisites

### Option 1: Docker (Recommended)
- Docker Engine 20.10+
- Docker Compose 2.0+

### Option 2: Local Development
- Python 3.12+
- Node.js 20+ LTS
- Redis 7+
- SQLite3

## Quick Start

### Docker Setup (Easiest)

```bash
cd /home/markus/Documents/Knockout/knockoutJS/Mrieg_com_fastAPI_v0_3

# Start services (Redis, API, Worker in containers)
./start.sh

# Start with image rebuild (if Dockerfile changed)
./start.sh build
```

The server will be available at `http://localhost:8000`

- **API endpoints**: `http://localhost:8000/games/api/*`
- **Game page**: `http://localhost:8000/games/knockout?game_id=<game_id>`

### Local Development Setup

#### 1. Create Virtual Environment
```bash
cd /home/markus/Documents/Knockout/knockoutJS/Mrieg_com_fastAPI_v0_3
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

#### 2. Start Redis (Required)
```bash
redis-server  # Ensure Redis is running on localhost:6379
```

#### 3. Initialize Database
```bash
python scripts/init_sqlite.py
```

#### 4. Start API Server
```bash
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### 5. Start Celery Worker (in another terminal)
```bash
# Ensure venv is activated
celery -A workers.celery_app worker --loglevel=info
```

The server is now running locally at `http://localhost:8000`

## API Endpoints

### Game Management
- `POST /games/api/create_game` - Create a new game
- `POST /games/api/join_game` - Join an existing game
- `POST /games/api/leave_game` - Leave a game
- `POST /games/api/delete_game` - Delete a game (creator only)

### Gameplay
- `POST /games/api/start_game` - Initialize game and create pieces
- `POST /games/api/submit_turn` - Submit moves for current turn
- `POST /games/api/apply_moves_and_run_game` - Manually advance turn and run simulation
- `GET /games/api/game_state` - Fetch current game state

### Authentication
- `POST /games/api/create_player` - Register a new player
- Credentials passed via cookies (game:GAME_ID and player:PLAYER_ID)

## Data Models

### CreateGameRequest
```python
{
  "game_id": "string",
  "password": "string",
  "start_delay": 86400,  # seconds until auto-start
  "settings": {
    "max_players": 4,
    "board_size": 800,
    "board_shrink": 50,      # shrinkage per turn
    "turn_interval": 86400   # seconds between turns
  }
}
```

### ApplyMovesAndRunGameRequest
```python
{
  "game_id": "string",
  "turn_number": 5  # Client's view of current turn (prevents race conditions)
}
```

### SubmitTurnRequest
```python
{
  "game_id": "string",
  "player_id": "string",
  "turn_number": 5,
  "actions": [
    {
      "pieceid": "0",
      "vx": 10.5,      # X velocity
      "vy": -5.3       # Y velocity
    }
  ]
}
```

## Project Structure

```
├── main.py                 # FastAPI app initialization
├── config.py              # Configuration (Redis URL, DB path, etc.)
├── requirements.txt       # Python dependencies
├── Dockerfile             # Container image definition
├── docker-compose.yml     # Multi-service orchestration
├── start.sh               # Launcher script (supports --build flag)
│
├── routes/
│   ├── games.py           # Game HTTP endpoints
│   ├── games_helpers.py   # Game business logic
│   ├── auth.py            # Authentication endpoints
│   └── players.py         # Player management
│
├── stores/
│   ├── game_store.py      # Abstract store interface
│   ├── sqlite_game_store.py # SQLite implementation with atomic operations
│   └── sqlite_auth_store.py # Password/credential storage
│
├── models/
│   ├── api_models.py      # Pydantic request/response models
│   └── domain_models.py   # Internal typed dicts
│
├── services/
│   └── game_simulation.py # Physics engine interface (calls Node.js)
│
├── static/
│   ├── game.html          # Game viewport
│   ├── index.html         # Lobby page
│   ├── ui.js              # Game state and rendering
│   ├── ui_buttons.js      # Control panel
│   └── physics.js         # Client-side physics preview
│
├── workers/
│   ├── celery_app.py      # Celery configuration
│   ├── tasks.py           # Background tasks (run_turn, start_game)
│   └── task_helpers.py    # Task utilities
│
├── db/
│   ├── schema.sql         # Database initialization
│   └── connections.py     # Database connection pooling
│
├── scripts/
│   ├── init_sqlite.py     # Database setup script
│   └── start_api.sh       # API startup with Node.js detection
│
└── utils/
    ├── cookies.py         # Session token handling
    ├── validation.py      # Input validation
    └── time.py            # Timezone utilities
```

## Database

SQLite database (`dev.db`) stores:
- **games**: Game metadata, creator, start time
- **game_settings**: Board size, player limits, turn intervals
- **game_state**: Current turn number, locks, timestamps
- **game_players**: Player-to-game assignments, colors, submission status
- **pieces**: Piece positions, velocities, ownership
- **pieces_old**: Previous turn state snapshot
- **players**: Player registry
- **game_passwords**: Hashed game passwords
- **player_passwords**: Hashed player credentials

**Locking Strategy:**
- Turn number validation prevents stale scheduled tasks from advancing 

## Testing

Run a game creation flow:
```bash
curl -X POST http://localhost:8000/games/api/create_game \
  -H "Content-Type: application/json" \
  -d '{
    "game_id": "test_game",
    "password": "test123",
    "settings": {"max_players": 2, "turn_interval": 60}
  }'
```

Access game at: `http://localhost:8000/games/knockout?game_id=test_game`

## Deployment Notes

- **Dockerfile**: Uses Python 3.12-slim base, installs Node.js at build time
- **User management**: API runs as root (0:0) for initialization, Worker runs as unprivileged appuser (1000:1000)
- **Database permissions**: Database file set to 0o666 for multi-process access
- **Transaction isolation**: Set to `isolation_level=None` to allow explicit transaction control
- **Journal mode**: Switched to DELETE mode to avoid Docker volume locking with WAL

## Development Workflow (Myself, cloudflared + linux)

1. **Make code changes** in Python/JS files
2. **Restart services**: close terminals, then run start.sh, with 'b' as an arg to rebuild the docker image
3. **Check logs**: View output in terminal windows (or `docker-compose logs -f api`)
4. **Database reset**: Happens automatically with start.sh

## Development Workflow if not using start.sh

1. **Make code changes** in Python/JS files
2. **Restart services**: `docker-compose restart api` (or `worker` service)
3. **Check logs**: View output in terminal windows or `docker-compose logs -f api`
4. **Database reset**: Delete `dev.db*` files and restart to reinitialize

## Performance Tuning

- **SQLite timeout**: Set to 30s in `sqlite_game_store.py` for concurrent access
- **Redis persistence**: Disable for development (enabled by default in `docker-compose.yml`)
- **Node.js simulation**: Runs synchronously; consider async wrapper for 100+ pieces

## Further Resources

- **FastAPI docs**: https://fastapi.tiangolo.com
- **Celery docs**: https://docs.celeryproject.org
- **SQLite async**: https://github.com/omnilib/aiosqlite
