from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone

from game_routes_new import router as game_router
from game_simulation import run_daily_game_updates

# --- FastAPI setup ---
app = FastAPI()

# --- Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://mrieg.com"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# --- HTML Homepage ---
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/static/index.html")
    
# Receive the POST when the rickroll button is clicked @app.post("/rickroll-hit") 
async def rickroll_hit(request: Request): 
    data = await request.json() 
    print("Rickroll clicked:", data) 
    return {"status": "ok"}


@app.get("/api/devtool")
async def submit_turn(request: Request):
    run_js_simulation()
    return {"Simulations ran early, as requested."}


# --- Register routes ---
app.include_router(game_router, prefix="/games")

# --- Scheduler setup ---
scheduler = BackgroundScheduler(timezone=timezone("America/Toronto"))
scheduler.add_job(run_daily_game_updates, trigger="cron", hour=0, minute=0)  # midnight Toronto time
scheduler.start()

@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()
