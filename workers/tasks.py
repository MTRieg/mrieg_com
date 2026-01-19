"""Celery task definitions for the game server."""
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded
import logging
from datetime import datetime, UTC
from typing import Any, Dict
import asyncio
from functools import wraps
import stores
from .task_helpers import createGenericGameName
from workers.celery_app import app
from stores import (
	GameNotFound,
	TurnMismatch,
	InvalidState,
	SimulationError,
	UnexpectedResult,
)

logger = logging.getLogger(__name__)

soft_time_limit = 60  # seconds
hard_time_limit = 180  # seconds

heavy_task_soft_time_limit = 120  # seconds
heavy_task_hard_time_limit = 300  # seconds




def celery_task(**task_kwargs):
	"""Combined decorator that registers a Celery task and adds error handling.
	
	Replaces the need for @app.task() and @celery_task_error_handler separately.
	Automatically:
	- Registers the function as a Celery task via @app.task()
	- Wraps execution with error handling (SoftTimeLimitExceeded, generic exceptions)
	- For retryable exceptions: logs and re-raises to allow Celery's autoretry mechanism
	- For non-retryable exceptions: logs and returns graceful failure dict
	
	Usage:
		@celery_task(bind=True, queue="game_turns", ...)
		def my_task(self, ...):
			# business logic
	"""
	def decorator(func):
		@wraps(func)
		def wrapper(self, *args, **kwargs):
			try:
				return func(self, *args, **kwargs)
			except SoftTimeLimitExceeded:
				logger.warning(f"{func.__name__} exceeded soft time limit, graceful shutdown")
				raise
			except Exception as exc:
				# Check if exception is retryable (default to True for unknown exceptions)
				is_retryable = getattr(exc, 'retryable', True)
				
				if not is_retryable:
					logger.error(f"{func.__name__} failed with non-retryable error: {exc.__class__.__name__}: {exc}", exc_info=True)
					# Return graceful failure dict instead of raising (prevents Celery retry)
					return {
						"status": "failure",
						"error": exc.__class__.__name__,
						"message": str(exc),
						"timestamp": datetime.now(UTC).isoformat(),
					}
				else:
					logger.error(f"{func.__name__} failed with retryable error: {exc.__class__.__name__}: {exc}", exc_info=True)
					raise
		# Register as Celery task with error handling
		return app.task(base=GameServerTask, **task_kwargs)(wrapper)
	return decorator


class GameServerTask(Task):
    """Base task class with custom error handling and logging."""
    
    autoretry_for = (Exception,)
    retry_kwargs = {"max_retries": 5}
    retry_backoff = True
    retry_backoff_max = 3600
    retry_jitter = True
    
    def on_retry(self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo: Any) -> None:
        """Log retry events."""
        logger.warning(
            f"Task {self.name} (id={task_id}) retrying after {exc}",
            extra={"task_id": task_id, "task_args": args, "task_kwargs": kwargs},
        )
    
    def on_failure(self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo: Any) -> None:
        """Log task failures."""
        logger.error(
            f"Task {self.name} (id={task_id}) failed with {exc}",
            extra={"task_id": task_id, "task_args": args, "task_kwargs": kwargs},
            exc_info=einfo,
        )
    
    def on_success(self, result: Any, task_id: str, args: tuple, kwargs: dict) -> None:
        """Log task successes."""
        logger.info(
            f"Task {self.name} (id={task_id}) succeeded",
            extra={"task_id": task_id, "task_result": result},
        )


@celery_task(
    bind=True,
    name="workers.tasks.repopulate_unused_game_ids",
    queue="maintenance",
    priority=2,
    soft_time_limit=soft_time_limit,
    time_limit=hard_time_limit,
)
def repopulate_unused_game_ids(self, gameNamesTarget = 200) -> Dict[str, Any]:
    """
    Periodic task to refresh unused game IDs (every 6 hours).
    
    Args:
        gameNamesTarget: minimum number of unused game IDs to maintain (default 200)
    
    Returns:
        dict: {
            "status": "success" | "partial_failure" | "failure",
            "refreshed_count": int,
            "added_count": int,
            "current_count": int,
            "errors": list[str] (optional),
        }
    """
    logger.info(f"Starting repopulate_unused_game_ids task (target={gameNamesTarget})")

    try:
        gs = stores.get_game_store()
    except RuntimeError:
        raise RuntimeError("stores not initialized in worker")

    # 1. Get count of current unused game IDs
    current_count = asyncio.run(gs.count_unused_game_ids())
    logger.info(f"Current unused game IDs: {current_count}")
    
    refreshed_count = 0
    added_count = 0
    errors = []

    # 2. If below threshold, generate new names
    if current_count < gameNamesTarget:
        needed = gameNamesTarget - current_count
        logger.info(f"Below target: generating {needed} new game names")
        
        new_names = []
        try:
            for _ in range(needed):
                new_name = createGenericGameName()
                new_names.append(new_name)
            
            # 3. Add them to the unused pool
            inserted = asyncio.run(gs.add_unused_game_ids(new_names))
            added_count = inserted
            logger.info(f"Added {inserted} new game IDs to pool")
            
        except Exception as exc:
            logger.error(f"Failed to generate or add game names: {exc}", exc_info=True)
            errors.append(f"name generation/insertion: {str(exc)}")
    else:
        logger.info(f"At or above target ({current_count} >= {gameNamesTarget}), no generation needed")
    
    # Get final count
    final_count = asyncio.run(gs.count_unused_game_ids())
    
    result = {
        "status": "success",
        "refreshed_count": refreshed_count,
        "added_count": added_count,
        "current_count": final_count,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    
    if errors:
        result["errors"] = errors
        result["status"] = "partial_failure"
    
    logger.info(f"repopulate_unused_game_ids task completed: {result}")
    return result


@celery_task(
    bind=True,
    name="workers.tasks.run_turn",
    queue="game_turns",
    priority=1,
    soft_time_limit=heavy_task_soft_time_limit,
    time_limit=heavy_task_hard_time_limit,
)
def run_turn(self, game_id: str, turn_number: int, scheduled_at: str | None = None) -> Dict[str, Any]:
    """
    Process a game turn for `game_id` and `turn_number`.
    
    Calls the run_game helper to execute a single turn of gameplay.
    
    Args:
        game_id: ID of the game to run a turn for
        turn_number: Turn number being processed (for logging/tracking)
        scheduled_at: ISO timestamp when this turn was scheduled (optional)
    
    Returns:
        dict: Result from run_game helper with status, state changes, etc.
        
    Raises:
        GameNotFound: if game no longer exists
        TurnMismatch: if turn has already advanced (stale task)
        InvalidState: if game state is invalid
        SimulationError: if physics simulation fails
        UnexpectedResult: if unexpected error occurs
    """
    logger.info(f"run_turn called for game_id={game_id} turn_number={turn_number}")
    
    try:
        gs = stores.get_game_store()
    except RuntimeError:
        raise RuntimeError("stores not initialized in worker")
    
    # Import here to avoid circular imports
    from routes import games_helpers
    
    # Run the turn using the game helper
    # Pass turn_number so store can verify this is the expected turn (catches stale scheduled tasks)
    result = asyncio.run(games_helpers.apply_moves_and_run_game(
        store=gs,
        game_id=game_id,
        turn_number=turn_number,
    ))
    
    result["turn_number"] = turn_number
    if scheduled_at:
        result["scheduled_at"] = scheduled_at
    
    logger.info(f"run_turn completed for game_id={game_id}: {result}")
    return result


@celery_task(
    bind=True,
    name="workers.tasks.start_game",
    queue="game_management",
    priority=1,
    soft_time_limit=soft_time_limit,
    time_limit=hard_time_limit,
)
def start_game(self, game_id: str, *, scheduled_at: str | None = None) -> Dict[str, Any]:
    """
    Start the specified game.
    
    Transitions a game from waiting/setup state to active/running state,
    typically triggered by a scheduled task or manual admin action.
    
    Args:
        game_id: ID of the game to start
        scheduled_at: ISO timestamp when this start was scheduled (optional)
    
    Returns:
        dict: Result from start_game helper with status, initial state, etc.
    """
    logger.info(f"start_game called for game_id={game_id}")
    owner_id = "system"  # Reserved name for system-triggered starts
    
    try:
        gs = stores.get_game_store()
    except RuntimeError:
        raise RuntimeError("stores not initialized in worker")
    
    # Import here to avoid circular imports
    from routes import games_helpers

    # Combined async operation to avoid multiple asyncio.run() calls
    # and to apply a timeout to the entire operation
    async def combined_start_game():
        """Start game in a single event loop with timeout."""
        # Start the game with a timeout
        try:
            result = await asyncio.wait_for(
                games_helpers.start_game(
                    store=gs,
                    game_id=game_id,
                    owner_id=owner_id,
                ),
                timeout=45.0
            )
            return result
        except asyncio.TimeoutError:
            logger.error("start_game timed out after 45s for game_id=%s", game_id)
            raise RuntimeError(f"start_game helper timeout for {game_id}")
        except Exception:
            logger.exception("start_game helper raised exception for game_id=%s", game_id)
            raise
    
    try:
        result = asyncio.run(combined_start_game())
    except Exception:
        logger.exception("Combined start_game operation failed for game_id=%s", game_id)
        raise
    
    if scheduled_at:
        result["scheduled_at"] = scheduled_at
    
    logger.info(f"start_game completed for game_id={game_id}: {result}")
    return result


@celery_task(
    bind=True,
    name="workers.tasks.clear_stale_leases",
    queue="maintenance",
    priority=2,
    soft_time_limit=soft_time_limit,
    time_limit=hard_time_limit,
)
def clear_stale_leases(self) -> Dict[str, Any]:
    """
    Periodic task to clear stale leases on unused game IDs.
    
    Leases prevent a game ID from being reassigned if the reserving process
    crashes. This task clears leases that have expired (leased_until < now),
    making those IDs available again.
    
    Returns:
        dict: {
            "status": "success" | "failure",
            "cleared_count": int,
            "timestamp": str,
            "errors": list[str] (optional),
        }
    """
    logger.info("Starting clear_stale_leases task")

    try:
        gs = stores.get_game_store()
    except RuntimeError:
        raise RuntimeError("stores not initialized in worker")

    # Clear all expired leases
    cleared_count = asyncio.run(gs.clear_stale_leases())
    logger.info(f"Cleared {cleared_count} stale leases")
    
    result = {
        "status": "success",
        "cleared_count": cleared_count,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    
    logger.info(f"clear_stale_leases task completed: {result}")
    return result


@celery_task(
    bind=True,
    name="workers.tasks.delete_expired_session_tokens",
    queue="maintenance",
    priority=2,
    soft_time_limit=soft_time_limit,
    time_limit=hard_time_limit,
)
def delete_expired_session_tokens(self, inactivity_hours: int = 48) -> Dict[str, Any]:
    """
    Periodic task to delete expired session tokens.
    
    Args:
        inactivity_hours: number of hours of inactivity before expiry (not used here,
                         sessions use their own expires_at timestamp from creation)
    
    Returns:
        dict: {
            "status": "success" | "failure",
            "deleted_count": int,
            "timestamp": str,
        }
    """
    logger.info("Starting delete_expired_session_tokens task")

    try:
        au = stores.get_auth_store()
    except RuntimeError:
        raise RuntimeError("stores not initialized in worker")

    # Delete all expired sessions from the database
    deleted_count = asyncio.run(au.delete_expired_sessions())
    logger.info(f"Deleted {deleted_count} expired session tokens")
    
    result = {
        "status": "success",
        "deleted_count": deleted_count,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    
    logger.info(f"delete_expired_session_tokens task completed: {result}")
    return result


@celery_task(
    bind=True,
    name="workers.tasks.delete_stale_games",
    queue="maintenance",
    priority=2,
    soft_time_limit=heavy_task_soft_time_limit,
    time_limit=heavy_task_hard_time_limit,
)
def delete_stale_games(self, inactivity_days: int = 30) -> Dict[str, Any]:
    """
    Periodic task to delete games not accessed for a prolonged period.
    
    Args:
        inactivity_days: number of days of inactivity before deletion (default 30)
    
    Returns:
        dict: {
            "status": "success" | "failure",
            "deleted_count": int,
            "timestamp": str,
        }
    """
    logger.info(f"Starting delete_stale_games task (inactivity_days={inactivity_days})")

    try:
        gs = stores.get_game_store()
    except RuntimeError:
        raise RuntimeError("stores not initialized in worker")

    # Delete all stale games from the database
    deleted_count = asyncio.run(gs.delete_stale_games(inactivity_days))
    logger.info(f"Deleted {deleted_count} stale games")
    
    result = {
        "status": "success",
        "deleted_count": deleted_count,
        "inactivity_days": inactivity_days,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    
    logger.info(f"delete_stale_games task completed: {result}")
    return result


@celery_task(
    bind=True,
    name="workers.tasks.delete_stale_players",
    queue="maintenance",
    priority=2,
    soft_time_limit=heavy_task_soft_time_limit,
    time_limit=heavy_task_hard_time_limit,
)
def delete_stale_players(self, inactivity_days: int = 30) -> Dict[str, Any]:
    """
    Periodic task to delete orphaned players older than a threshold.
    
    Only deletes players not associated with any active games and older than
    `inactivity_days` days.
    
    Args:
        inactivity_days: number of days since creation before deletion (default 30)
    
    Returns:
        dict: {
            "status": "success" | "failure",
            "deleted_count": int,
            "timestamp": str,
        }
    """
    logger.info(f"Starting delete_stale_players task (inactivity_days={inactivity_days})")

    try:
        gs = stores.get_game_store()
    except RuntimeError:
        raise RuntimeError("stores not initialized in worker")

    # Delete all stale players from the database
    deleted_count = asyncio.run(gs.delete_stale_players(inactivity_days))
    logger.info(f"Deleted {deleted_count} stale players")
    
    result = {
        "status": "success",
        "deleted_count": deleted_count,
        "inactivity_days": inactivity_days,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    
    logger.info(f"delete_stale_players task completed: {result}")
    return result
