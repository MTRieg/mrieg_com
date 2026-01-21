#!/usr/bin/env bash
set -euo pipefail

source ./venv/bin/activate

# Set database path to match the API server (dev.db, not db.sqlite3)
export MRIEG_DB_PATH="${MRIEG_DB_PATH:-./dev.db}"

# Don't override environment variables - let docker-compose set them
# In Docker, 'localhost' refers to the container itself, not other services
# Use 'redis' as the hostname (docker-compose service name)

# start beat scheduler with Redis-backed persistence
exec celery -A workers.celery_app beat \
  --loglevel=info \
  --scheduler celery_beat_redis:RedisScheduler
