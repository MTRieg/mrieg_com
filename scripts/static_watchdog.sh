#!/bin/bash
#
# Static File Watchdog
# Monitors static file availability and auto-recovers when issues are detected.
# Logs all activity and captures diagnostic information on failures.
#

# note that this should only exist temporarily; if the problem doesn't happen again I'll remove it, but
# there's also the chance that "nothing is as permanent as a temporary solution that works" keeps this alive

# also, the config values here, especially tunnel name and URLs, need to be adjusted for different deployments

set -u

# Configuration
PROJECT_DIR="$HOME/Documents/Knockout/knockoutJS/Mrieg_com_fastAPI_v0_3"
LOG_DIR="$PROJECT_DIR/watchdog_logs"
CHECK_INTERVAL=300  # 5 minutes in seconds
CLOUDFLARE_URL="https://tests.mrieg.com/static/ui.js"
LOCALHOST_URL="http://localhost:8000/static/ui.js"
TUNNEL_NAME="experimental_tunnel"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Log file paths
MAIN_LOG="$LOG_DIR/watchdog.log"
FAILURE_LOG="$LOG_DIR/failures.log"

# Helper: timestamp
timestamp() {
    date "+%Y-%m-%d %H:%M:%S"
}

# Helper: log to main log
log() {
    echo "[$(timestamp)] $1" | tee -a "$MAIN_LOG"
}

# Helper: log failure with details
log_failure() {
    echo "[$(timestamp)] FAILURE: $1" | tee -a "$MAIN_LOG" "$FAILURE_LOG"
}

# Capture diagnostic logs on failure
capture_diagnostics() {
    local failure_id="$1"
    local diag_dir="$LOG_DIR/failure_$failure_id"
    mkdir -p "$diag_dir"
    
    log "Capturing diagnostics to $diag_dir"
    
    # Docker API logs (last 100 lines)
    docker logs --tail 100 mrieg_com_fastapi_v0_3_api_1 > "$diag_dir/docker_api.log" 2>&1 || \
        docker logs --tail 100 mrieg_com_fastapi_v0_3-api-1 > "$diag_dir/docker_api.log" 2>&1 || \
        echo "Could not get docker logs" > "$diag_dir/docker_api.log"
    
    # Docker worker logs
    docker logs --tail 50 mrieg_com_fastapi_v0_3_worker_1 > "$diag_dir/docker_worker.log" 2>&1 || \
        docker logs --tail 50 mrieg_com_fastapi_v0_3-worker-1 > "$diag_dir/docker_worker.log" 2>&1 || \
        echo "Could not get worker logs" > "$diag_dir/docker_worker.log"
    
    # Docker container status
    docker ps -a > "$diag_dir/docker_ps.log" 2>&1
    
    # Cloudflared process info
    ps aux | grep -E "cloudflared|tunnel" > "$diag_dir/cloudflared_process.log" 2>&1
    
    # Network connections to port 8000
    ss -tlnp | grep 8000 > "$diag_dir/port_8000.log" 2>&1
    
    # System resource usage
    free -h > "$diag_dir/memory.log" 2>&1
    df -h > "$diag_dir/disk.log" 2>&1
    
    # Curl verbose output for both endpoints
    curl -v --max-time 10 "$CLOUDFLARE_URL" > "$diag_dir/curl_cloudflare.log" 2>&1
    curl -v --max-time 10 "$LOCALHOST_URL" > "$diag_dir/curl_localhost.log" 2>&1
    
    # Open file descriptors for uvicorn/python
    for pid in $(pgrep -f "uvicorn|python.*main"); do
        ls -la /proc/$pid/fd 2>/dev/null | wc -l >> "$diag_dir/fd_count.log"
    done 2>/dev/null || echo "Could not count file descriptors" > "$diag_dir/fd_count.log"
    
    log "Diagnostics captured"
}

# Restart cloudflared tunnel
restart_cloudflared() {
    log "Restarting cloudflared tunnel..."
    
    # Kill existing cloudflared processes
    pkill -f "cloudflared.*tunnel.*run" || true
    sleep 2
    
    # Start new tunnel in background
    nohup cloudflared tunnel run "$TUNNEL_NAME" >> "$LOG_DIR/cloudflared.log" 2>&1 &
    local new_pid=$!
    
    sleep 5
    
    # Verify it started
    if ps -p $new_pid > /dev/null 2>&1; then
        log "Cloudflared restarted successfully (PID: $new_pid)"
        return 0
    else
        log_failure "Cloudflared failed to restart"
        return 1
    fi
}

# Restart docker services
restart_docker() {
    log "Restarting Docker services..."
    
    cd "$PROJECT_DIR"
    
    # Stop and restart docker-compose
    docker-compose down --remove-orphans 2>/dev/null || true
    sleep 3
    
    # Start services (preserve data - don't use --build unless necessary)
    docker-compose up -d
    
    # Wait for services to be healthy
    local retries=30
    while [ $retries -gt 0 ]; do
        if curl -sf "$LOCALHOST_URL" > /dev/null 2>&1; then
            log "Docker services restarted and responding"
            return 0
        fi
        sleep 2
        retries=$((retries - 1))
    done
    
    log_failure "Docker services failed to respond after restart"
    return 1
}

# Check if static files are accessible
check_cloudflare() {
    curl -sf --max-time 15 "$CLOUDFLARE_URL" > /dev/null 2>&1
}

check_localhost() {
    curl -sf --max-time 10 "$LOCALHOST_URL" > /dev/null 2>&1
}

# Main monitoring loop
main() {
    log "=========================================="
    log "Static File Watchdog started"
    log "Cloudflare URL: $CLOUDFLARE_URL"
    log "Localhost URL: $LOCALHOST_URL"
    log "Check interval: ${CHECK_INTERVAL}s"
    log "=========================================="
    
    local consecutive_failures=0
    local check_count=0
    
    while true; do
        check_count=$((check_count + 1))
        
        if check_cloudflare; then
            # Success
            if [ $consecutive_failures -gt 0 ]; then
                log "Recovery confirmed after $consecutive_failures failures"
            fi
            consecutive_failures=0
            
            # Log periodic health check (every 12 checks = 1 hour)
            if [ $((check_count % 12)) -eq 0 ]; then
                log "Health check #$check_count: OK"
            fi
        else
            # Cloudflare failed
            consecutive_failures=$((consecutive_failures + 1))
            failure_id=$(date "+%Y%m%d_%H%M%S")
            
            log_failure "Cloudflare check failed (failure #$consecutive_failures)"
            
            # Test localhost to determine which layer failed
            if check_localhost; then
                log_failure "Localhost OK - issue is cloudflare tunnel"
                
                # Capture diagnostics
                capture_diagnostics "${failure_id}_cf_only"
                
                # Restart cloudflared only
                restart_cloudflared
                
                # Verify fix
                sleep 10
                if check_cloudflare; then
                    log "Cloudflare tunnel restart fixed the issue"
                else
                    log_failure "Cloudflare still failing after tunnel restart"
                fi
            else
                log_failure "Localhost ALSO failed - issue is Docker/FastAPI"
                
                # Capture diagnostics
                capture_diagnostics "${failure_id}_docker"
                
                # Restart Docker first
                restart_docker
                sleep 5
                
                # Then restart cloudflared to ensure fresh connections
                restart_cloudflared
                
                # Verify fix
                sleep 10
                if check_cloudflare; then
                    log "Full restart fixed the issue"
                else
                    log_failure "Still failing after full restart"
                fi
            fi
        fi
        
        sleep "$CHECK_INTERVAL"
    done
}

# Handle shutdown gracefully
cleanup() {
    log "Watchdog shutting down..."
    exit 0
}
trap cleanup SIGINT SIGTERM

# Run
main
