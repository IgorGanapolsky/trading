#!/bin/bash
# Trading System Startup Script
# This script starts the trading system in the background

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
PID_FILE="$SCRIPT_DIR/trading_system.pid"

# Create logs directory
mkdir -p "$LOG_DIR"

# Check if already running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p $PID > /dev/null 2>&1; then
        echo "Trading system is already running (PID: $PID)"
        exit 1
    else
        echo "Stale PID file found, removing..."
        rm "$PID_FILE"
    fi
fi

# Load environment variables
if [ -f "$SCRIPT_DIR/.env" ]; then
    export $(cat "$SCRIPT_DIR/.env" | xargs)
fi

# Start the trading system
echo "Starting trading system..."
cd "$SCRIPT_DIR"
nohup python3 src/main.py --mode paper --log-level INFO > "$LOG_DIR/startup.log" 2>&1 &
PID=$!

# Save PID
echo $PID > "$PID_FILE"

echo "Trading system started (PID: $PID)"
echo "Logs: $LOG_DIR/trading_system.log"
echo ""
echo "To stop: ./stop_trading_system.sh"
echo "To check status: ./check_trading_status.sh"
