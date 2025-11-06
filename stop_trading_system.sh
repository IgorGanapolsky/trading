#!/bin/bash
# Trading System Stop Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/trading_system.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "PID file not found. Trading system may not be running."
    exit 1
fi

PID=$(cat "$PID_FILE")

if ps -p $PID > /dev/null 2>&1; then
    echo "Stopping trading system (PID: $PID)..."
    kill -SIGTERM $PID

    # Wait for graceful shutdown (max 10 seconds)
    for i in {1..10}; do
        if ! ps -p $PID > /dev/null 2>&1; then
            echo "Trading system stopped successfully"
            rm "$PID_FILE"
            exit 0
        fi
        sleep 1
    done

    echo "Force killing trading system..."
    kill -SIGKILL $PID
    rm "$PID_FILE"
    echo "Trading system force stopped"
else
    echo "Trading system is not running (stale PID file)"
    rm "$PID_FILE"
fi
