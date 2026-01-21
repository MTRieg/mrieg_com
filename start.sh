#!/usr/bin/env bash

# Define the project directory
PROJECT_DIR="$HOME/Documents/Knockout/knockoutJS/Mrieg_com_fastAPI_v0_3"

# Check if build/preserve flags are provided
BUILD_FLAG=""
PRESERVE_DATA=false
for arg in "$@"; do
	case "$arg" in
		build|--build|-b)
			BUILD_FLAG="--build"
			echo "Building Docker images..."
			;;
		prod|--prod|--production|--preserve|-p)
			PRESERVE_DATA=true
			echo "Production mode: preserving existing data..."
			;;
	esac
done

# Clean up any existing processes and services
echo "Cleaning up any existing services..."

# Kill any running sqlite3 processes
pkill -f "sqlite3" || true

# Kill any running cloudflared processes
pkill -f "cloudflared" || true

# Stop docker-compose if it's running
if command -v docker-compose &> /dev/null; then
	cd "$PROJECT_DIR"
	docker-compose down --remove-orphans 2>/dev/null || true
	
	# Only delete database and clear data in development mode (default)
	if [ "$PRESERVE_DATA" = false ]; then
		echo "Development mode: clearing database files and Redis queues..."
		# Clean up all database files including WAL and SHM to avoid lock issues
		rm -f dev.db db.sqlite3 db.sqlite3-journal dev.db-wal dev.db-shm db.sqlite3-wal db.sqlite3-shm
		# Remove Redis volume to clear task queues
		docker volume rm redis_data 2>/dev/null || true
	else
		echo "Production mode: preserving database and Redis queues..."
		# In production mode, data persists across restarts if volumes are configured
	fi
	
	cd - > /dev/null
fi

echo "Cleanup complete. Starting services..."

# Store PIDs of all child processes
pids=()

# Cleanup function to kill all background processes
cleanup() {
    echo "Shutting down all services..."
    for pid in "${pids[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    wait
}

# Set trap to cleanup on exit
trap cleanup EXIT INT TERM

# Start Docker Compose (Redis, API, Worker all in one)
xfce4-terminal --hold -T "Docker Services (Redis, API, Worker)" \
	--command "bash -c 'cd \"$PROJECT_DIR\" && sg docker \"docker-compose up $BUILD_FLAG\"; exec bash'" &
pids+=($!)

# Start Cloudflare Tunnel
xfce4-terminal --hold -T "Cloudflare Tunnel" \
	--command "bash -c 'cloudflared tunnel run mytunnel; exec bash'" &
pids+=($!)

# Wait for all processes
wait
