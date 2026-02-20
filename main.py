"""Minimal FastAPI application entrypoint for v0_3.

This file creates the FastAPI app and mounts route modules. Endpoints
are implemented as stubs in `routes/*` and will be filled in later.
"""
import mimetypes
import time

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

# Ensure JavaScript files are served with the correct MIME type
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/javascript", ".mjs")

from routes import games as games_routes
from routes import players as players_routes
from routes import auth as auth_routes
from routes import debug as debug_routes
from routes import nongame as nongame_routes
from stores import init_stores
import config
import logging

logger = logging.getLogger(__name__)

app = FastAPI(title="Mrieg Game API (v0_3)")


# Middleware to log all requests (helps debug static file issues)
class RequestLoggingMiddleware(BaseHTTPMiddleware):
	async def dispatch(self, request: Request, call_next):
		start_time = time.time()
		path = request.url.path
		
		# Log static file requests specifically to help debug
		if path.startswith("/static"):
			logger.info(f"Static request: {request.method} {path}")
		
		try:
			response = await call_next(request)
			process_time = time.time() - start_time
			
			# Log slow requests or static file responses
			if path.startswith("/static") or process_time > 1.0:
				logger.info(f"Response: {path} - {response.status_code} ({process_time:.3f}s)")
			
			return response
		except Exception as e:
			logger.error(f"Request failed: {path} - {type(e).__name__}: {e}")
			raise


app.add_middleware(RequestLoggingMiddleware)

# Mount static files with html=False to avoid directory listing issues
# and add follow_symlink=False for security
app.mount("/static", StaticFiles(directory="static", html=False, follow_symlink=False), name="static")

# Register routers (prefixes are adjustable as development progresses)
app.include_router(nongame_routes.router)  # Root route for index.html
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
