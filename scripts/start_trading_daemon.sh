#!/bin/bash
# Trading Daemon Starter
# Runs the trading scheduler in the background

cd /home/user/trading
source .venv/bin/activate 2>/dev/null || true

# Check if already running
if pgrep -f "python.*src/main.py" > /dev/null; then
    echo "Trading daemon already running"
    exit 0
fi

# Start the daemon
nohup python -m src.main > /home/user/trading/logs/trading_daemon.log 2>&1 &
echo $! > /home/user/trading/trading_daemon.pid
echo "Trading daemon started with PID: $(cat /home/user/trading/trading_daemon.pid)"
