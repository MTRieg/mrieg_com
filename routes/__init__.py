"""HTTP route modules (FastAPI routers) for the application.

This file explicitly exports the router objects provided by each
submodule so callers can do:

	from routes import games_router
	app.include_router(games_router, prefix="/games")

Submodules should expose an `APIRouter` named `router`.
"""

from .games import router as games_router
from .players import router as players_router
from .auth import router as auth_router
from .debug import router as debug_router

__all__ = [
	"games_router",
	"players_router",
	"auth_router",
	"debug_router",
]
