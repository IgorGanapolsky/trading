#!/bin/bash
# Trading System Stop Script

set -e

# Configuration
TRADING_DIR="/home/user/trading"
PID_FILE="${TRADING_DIR}/trading-system.pid"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if PID file exists
if [ ! -f "$PID_FILE" ]; then
    log_error "Trading system is not running (no PID file found)"
    exit 1
fi

# Read PID
PID=$(cat "$PID_FILE")

# Check if process is running
if ! ps -p "$PID" > /dev/null 2>&1; then
    log_warn "Process not found (PID: $PID)"
    rm -f "$PID_FILE"
    exit 1
fi

log_info "Stopping Trading System (PID: $PID)..."

# Send SIGTERM for graceful shutdown
kill -TERM "$PID"

# Wait for process to stop (max 30 seconds)
for i in {1..30}; do
    if ! ps -p "$PID" > /dev/null 2>&1; then
        log_info "Trading system stopped successfully"
        rm -f "$PID_FILE"
        exit 0
    fi
    sleep 1
done

# If still running, force kill
log_warn "Process did not stop gracefully, forcing shutdown..."
kill -KILL "$PID"
rm -f "$PID_FILE"
log_info "Trading system stopped (forced)"
