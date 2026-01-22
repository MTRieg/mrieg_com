"""Celery app configuration and task scheduling."""
import sys
import os
from pathlib import Path

print(f"[CELERY_INIT] celery_app.py starting import, CELERY_BROKER_URL={os.getenv('CELERY_BROKER_URL')}")
# Add project root to Python path so imports work when celery runs this module directly
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure timezone BEFORE importing anything else
import pytz
os.environ['TZ'] = 'UTC'

from celery import Celery
from celery.schedules import crontab
from kombu import Exchange, Queue
import logging
from stores import init_stores
import config

# Initialize Celery app
app = Celery("game_server")

# Load config from environment variables or defaults
broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

print(f"[CELERY] CELERY_BROKER_URL env var: {os.getenv('CELERY_BROKER_URL')}")
print(f"[CELERY] CELERY_RESULT_BACKEND env var: {os.getenv('CELERY_RESULT_BACKEND')}")
print(f"[CELERY] Using broker_url: {broker_url}")
print(f"[CELERY] Using result_backend: {result_backend}")

# Load config from a dedicated module or dict
app.config_from_object({
    "broker_url": broker_url,
    "result_backend": result_backend,
    "task_serializer": "json",
    "accept_content": ["json"],
    "result_serializer": "json",
    "timezone": pytz.UTC,
    "enable_utc": True,
    "task_acks_late": True,
    "worker_prefetch_multiplier": 1,
})

# Define queues
default_exchange = Exchange("default", type="direct")
game_turns_exchange = Exchange("game_turns", type="direct")
maintenance_exchange = Exchange("maintenance", type="direct")

app.conf.task_queues = (
    Queue(
        "default",
        exchange=default_exchange,
        routing_key="default",
        queue_arguments={"x-max-priority": 10},
    ),
    Queue(
        "game_turns",
        exchange=game_turns_exchange,
        routing_key="game_turns",
        queue_arguments={"x-max-priority": 10},
    ),
    Queue(
        "maintenance",
        exchange=maintenance_exchange,
        routing_key="maintenance",
        queue_arguments={"x-max-priority": 10},
    ),
)

# Default queue for tasks without explicit routing
app.conf.task_default_queue = "default"
app.conf.task_default_exchange = "default"
app.conf.task_default_routing_key = "default"

# Configure SQLAlchemy-backed Beat scheduler for production persistence
# The scheduler state is stored in a database (survives service restarts)
scheduler_db_url = os.getenv("CELERY_SCHEDULER_DB_URL", "sqlite:///celery_beat_schedule.db")

app.conf.beat_scheduler = 'celery_sqlalchemy_scheduler.schedulers:DatabaseScheduler'
app.conf.sqlalchemy_engine_options = {
    'url': scheduler_db_url,
}
app.conf.sqlalchemy_session_options = {}

# Periodic task schedules (Celery Beat)
app.conf.beat_schedule = {
    "repopulate-unused-game-ids": {
        "task": "workers.tasks.repopulate_unused_game_ids",
        "schedule": crontab(minute=0, hour="*/6"),  # Every 6 hours
        "options": {
            "queue": "maintenance",
            "priority": 2,  # Low priority
        },
    },
    "clear-stale-leases": {
        "task": "workers.tasks.clear_stale_leases",
        "schedule": crontab(minute=0, hour="*"),  # Every hour
        "options": {
            "queue": "maintenance",
            "priority": 2,
        },
    },
    "delete-expired-session-tokens": {
        "task": "workers.tasks.delete_expired_session_tokens",
        "schedule": crontab(minute=0, hour=0),  # Every 24 hours
        "options": {
            "queue": "maintenance",
            "priority": 2,
        },
    },
    "delete-stale-games": {
        "task": "workers.tasks.delete_stale_games",
        "schedule": crontab(minute=0, hour="*/48"),  # Every 48 hours
        "options": {
            "queue": "maintenance",
            "priority": 2,
        },
    },
    "delete-stale-players": {
        "task": "workers.tasks.delete_stale_players",
        "schedule": crontab(minute=0, hour="*/48"),  # Every 48 hours
        "options": {
            "queue": "maintenance",
            "priority": 2,
        },
    },
}

# Task configuration defaults
app.conf.task_default_retry_delay = 60
app.conf.task_max_retries = 5

logger = logging.getLogger(__name__)

# NOTE: Stores are NOT initialized here at module import time.
# In Celery worker processes, initializing aiosqlite connections at import time causes
# asyncio event loop context issues - the connection is created in one context but used
# in another, causing hangs/timeouts.
#
# Instead, stores are initialized lazily on first use within each task's event loop,
# or accessed via module-level singletons that are initialized when needed.
# See: stores/__init__.py init_stores() which handles this gracefully.

# Tasks are already imported in workers/__init__.py to avoid circular recursion
# No need to import them again here
