#!/bin/bash
# Trading System Status Script

set -e

# Configuration
TRADING_DIR="/home/user/trading"
PID_FILE="${TRADING_DIR}/trading-system.pid"
LOG_DIR="${TRADING_DIR}/logs"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Trading System Status${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if PID file exists
if [ ! -f "$PID_FILE" ]; then
    echo -e "Status: ${RED}STOPPED${NC}"
    echo "No PID file found"
    exit 0
fi

# Read PID
PID=$(cat "$PID_FILE")

# Check if process is running
if ps -p "$PID" > /dev/null 2>&1; then
    echo -e "Status: ${GREEN}RUNNING${NC}"
    echo "PID: $PID"

    # Get process info
    echo ""
    echo "Process Info:"
    ps -p "$PID" -o pid,ppid,%cpu,%mem,etime,cmd

    # Get latest logs
    if [ -f "${LOG_DIR}/trading_system.log" ]; then
        echo ""
        echo "Latest Log Entries:"
        echo "-------------------"
        tail -n 5 "${LOG_DIR}/trading_system.log"
    fi

    # Check log file size
    if [ -f "${LOG_DIR}/trading_system.log" ]; then
        LOG_SIZE=$(du -h "${LOG_DIR}/trading_system.log" | cut -f1)
        echo ""
        echo "Log File Size: $LOG_SIZE"
    fi
else
    echo -e "Status: ${RED}STOPPED${NC}"
    echo "PID file exists but process not running (stale PID: $PID)"
    echo "Run: rm ${PID_FILE}"
fi

echo ""
