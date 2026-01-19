"""Workers package: Celery app and background task definitions.

This package contains the Celery application instance and task modules.

Public API:
- `celery_app`: Celery application instance and configuration
- `tasks`: task implementations (e.g. `repopulate_unused_game_ids`)
"""

# Import tasks early to register Celery decorators before lazy loading
try:
    from . import tasks as _tasks_module
except ImportError:
    _tasks_module = None

# Lazy imports to avoid circular dependencies
def __getattr__(name):
    if name == "celery_app":
        from .celery_app import app
        return app
    elif name == "tasks":
        # Return already-imported tasks module if available
        if _tasks_module is not None:
            return _tasks_module
        from . import tasks
        return tasks
    elif name in (
        "repopulate_unused_game_ids",
        "run_turn",
        "start_game",
        "clear_stale_leases",
        "delete_expired_session_tokens",
        "delete_stale_games",
        "delete_stale_players",
    ):
        from .tasks import (
            repopulate_unused_game_ids,
            run_turn,
            start_game,
            clear_stale_leases,
            delete_expired_session_tokens,
            delete_stale_games,
            delete_stale_players,
        )
        return locals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "celery_app",
    "tasks",
    "repopulate_unused_game_ids",
    "run_turn",
    "start_game",
    "clear_stale_leases",
    "delete_expired_session_tokens",
    "delete_stale_games",
    "delete_stale_players",
]
