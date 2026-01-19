#!/usr/bin/env bash
set -euo pipefail

source ./venv/bin/activate

# Set database path to match the API server (dev.db, not db.sqlite3)
export MRIEG_DB_PATH="${MRIEG_DB_PATH:-./dev.db}"

# Don't override environment variables - let docker-compose set them
# In Docker, 'localhost' refers to the container itself, not other services
# Use 'redis' as the hostname (docker-compose service name)

# concurrency = number of CPU cores (for CPU-bound tasks set to cores; for IO-bound you can raise it)
CONCURRENCY=$(nproc)

# start a worker that listens to the configured queues
exec celery -A workers.celery_app worker \
  --loglevel=info \
  -Q game_turns,game_management,maintenance \
  -c "$CONCURRENCY"