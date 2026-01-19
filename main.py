"""Minimal FastAPI application entrypoint for v0_3.

This file creates the FastAPI app and mounts route modules. Endpoints
are implemented as stubs in `routes/*` and will be filled in later.
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from routes import games as games_routes
from routes import players as players_routes
from routes import auth as auth_routes
from routes import debug as debug_routes
from stores import init_stores
import config

app = FastAPI(title="Mrieg Game API (v0_3)")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Register routers (prefixes are adjustable as development progresses)
app.include_router(games_routes.router, prefix="/games")
app.include_router(players_routes.router, prefix="/games")
app.include_router(auth_routes.router, prefix="/games")
app.include_router(debug_routes.router, prefix="/games")


@app.on_event("startup")
async def startup_event():
	# Initialize shared store singletons for this process
	init_stores(config.DB_PATH)


@app.get("/healthz")
def healthz():
	return {"status": "ok"}
