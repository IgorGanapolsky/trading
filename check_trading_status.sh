#!/bin/bash
# Trading System Status Check

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/trading_system.pid"
LOG_FILE="$SCRIPT_DIR/logs/trading_system.log"

echo "==================================================================="
echo "TRADING SYSTEM STATUS"
echo "==================================================================="
echo ""

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p $PID > /dev/null 2>&1; then
        echo "✅ Status: RUNNING"
        echo "   PID: $PID"
        echo "   Uptime: $(ps -o etime= -p $PID)"
        echo ""
    else
        echo "❌ Status: STOPPED (stale PID file)"
        echo ""
    fi
else
    echo "❌ Status: NOT RUNNING"
    echo ""
fi

# Show recent logs
if [ -f "$LOG_FILE" ]; then
    echo "Recent logs (last 20 lines):"
    echo "-------------------------------------------------------------------"
    tail -20 "$LOG_FILE"
    echo "-------------------------------------------------------------------"
    echo ""
fi

# Show account status using daily_checkin
if [ -f "$SCRIPT_DIR/scripts/daily_checkin.py" ]; then
    echo ""
    echo "Running daily check-in report..."
    echo "==================================================================="
    python3 "$SCRIPT_DIR/scripts/daily_checkin.py"
fi
