#!/usr/bin/env bash
set -euo pipefail

# activate venv
source ./venv/bin/activate

# Use environment variables from docker-compose if available, otherwise set defaults
# MRIEG_DB_PATH is used by stores; DATABASE_URL is legacy
export MRIEG_DB_PATH="${MRIEG_DB_PATH:-./dev.db}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///./dev.db}"
export REDIS_URL="${REDIS_URL:-redis://redis:6379/0}"
export CELERY_BROKER_URL="${CELERY_BROKER_URL:-$REDIS_URL}"
export CELERY_RESULT_BACKEND="${CELERY_RESULT_BACKEND:-redis://redis:6379/1}"
export GAME_TIMEZONE="${GAME_TIMEZONE:-Toronto}"
# Node.js should be in PATH after Dockerfile build
NODE_BIN=$(which node 2>/dev/null || echo "")
if [ -z "$NODE_BIN" ]; then
	echo "Error: Node.js not found in PATH"
	exit 1
fi
export NODE_EXECUTABLE="$NODE_BIN"
export HEADLESS_SCRIPT="./static/headless.mjs"

# If a Node project exists, install production deps
if [ -f package.json ]; then
	echo "Installing Node dependencies from package.json"
	if [ -f package-lock.json ]; then
		npm ci --production || npm install --production
	else
		npm install --production
	fi
fi

# calculate workers = number of CPU cores (good for async uvicorn)
WORKERS=$(nproc)

# optional migrations step
# alembic upgrade head

# start the ASGI server bound to 0.0.0.0:8000 using Uvicorn workers
# Added timeout-keep-alive to prevent stale connections from consuming workers
# Added limit-max-requests to periodically recycle workers and prevent memory/fd leaks
exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers "$WORKERS" --log-level info \
	--timeout-keep-alive 65 \
	--limit-max-requests 10000