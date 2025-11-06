#!/bin/bash
# Trading System Startup Script
# This script can be used in any environment (systemd, supervisor, cron, or manual)

set -e

# Configuration
TRADING_DIR="/home/user/trading"
PYTHON_BIN="/usr/local/bin/python3"
LOG_DIR="${TRADING_DIR}/logs"
PID_FILE="${TRADING_DIR}/trading-system.pid"
MODE="${1:-paper}"
LOG_LEVEL="${2:-INFO}"

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

# Check if already running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        log_error "Trading system is already running (PID: $PID)"
        exit 1
    else
        log_warn "Removing stale PID file"
        rm -f "$PID_FILE"
    fi
fi

# Check environment
if [ ! -f "${TRADING_DIR}/.env" ]; then
    log_error ".env file not found at ${TRADING_DIR}/.env"
    log_info "Please copy .env.example to .env and configure your API keys"
    exit 1
fi

# Create log directory
mkdir -p "$LOG_DIR"

# Load environment variables
set -a
source "${TRADING_DIR}/.env"
set +a

# Validate critical environment variables
if [ -z "$ALPACA_API_KEY" ] || [ "$ALPACA_API_KEY" = "your_alpaca_api_key_here" ]; then
    log_error "ALPACA_API_KEY not configured in .env"
    exit 1
fi

if [ -z "$ALPACA_SECRET_KEY" ] || [ "$ALPACA_SECRET_KEY" = "your_alpaca_secret_key_here" ]; then
    log_error "ALPACA_SECRET_KEY not configured in .env"
    exit 1
fi

# Change to trading directory
cd "$TRADING_DIR"

log_info "Starting Trading System..."
log_info "  Mode: $MODE"
log_info "  Log Level: $LOG_LEVEL"
log_info "  Working Directory: $TRADING_DIR"
log_info "  Log Directory: $LOG_DIR"

# Start the trading system
exec "$PYTHON_BIN" "${TRADING_DIR}/src/main.py" \
    --mode "$MODE" \
    --log-level "$LOG_LEVEL" &

# Save PID
echo $! > "$PID_FILE"
log_info "Trading system started (PID: $!)"
log_info "Logs: ${LOG_DIR}/trading_system.log"
log_info ""
log_info "To stop: kill $(cat "$PID_FILE")"
log_info "To monitor: tail -f ${LOG_DIR}/trading_system.log"
