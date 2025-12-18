#!/bin/bash
#
# Local Trading Cron Backup Script
#
# This script provides a local fallback when GitHub Actions fails.
# Install via crontab to ensure trading runs even when GH Actions is dead.
#
# Installation:
#   crontab -e
#   # Add this line (runs at 9:35 AM ET on weekdays):
#   35 9 * * 1-5 /home/user/trading/scripts/local_trading_cron.sh >> /home/user/trading/logs/cron.log 2>&1
#
# For EST/EDT timezone handling, add both times:
#   35 13 * * 1-5 /home/user/trading/scripts/local_trading_cron.sh  # EST (14:35 UTC)
#   35 14 * * 1-5 /home/user/trading/scripts/local_trading_cron.sh  # EDT (13:35 UTC)
#
# Author: Trading System
# Created: 2025-12-18

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_ROOT/logs"
LOG_FILE="$LOG_DIR/local_trading_$(date +%Y-%m-%d).log"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=========================================="
log "LOCAL TRADING CRON - Starting"
log "=========================================="

cd "$PROJECT_ROOT"

# Check if we're in a virtual environment, activate if exists
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    log "Activated virtual environment"
fi

# Check if GitHub Actions ran today (avoid duplicate execution)
HEARTBEAT_FILE="$PROJECT_ROOT/data/scheduler_heartbeat.json"
if [ -f "$HEARTBEAT_FILE" ]; then
    LAST_RUN=$(python3 -c "
import json
from datetime import datetime, timezone
with open('$HEARTBEAT_FILE') as f:
    data = json.load(f)
last_run = data.get('last_run', '')
if last_run:
    dt = datetime.fromisoformat(last_run.replace('Z', '+00:00'))
    age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
    print(f'{age_hours:.1f}')
else:
    print('999')
" 2>/dev/null || echo "999")

    if (( $(echo "$LAST_RUN < 2" | bc -l) )); then
        log "GitHub Actions ran within last 2 hours (${LAST_RUN}h ago). Skipping local execution."
        log "=========================================="
        exit 0
    else
        log "GitHub Actions heartbeat stale (${LAST_RUN}h old). Running local backup."
    fi
else
    log "No heartbeat file found. GitHub Actions may be dead. Running local backup."
fi

# Load environment variables if .env exists
if [ -f "$PROJECT_ROOT/.env" ]; then
    export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
    log "Loaded environment from .env"
fi

# Verify critical environment variables
if [ -z "$ALPACA_API_KEY" ] || [ -z "$ALPACA_SECRET_KEY" ]; then
    log "ERROR: ALPACA_API_KEY or ALPACA_SECRET_KEY not set"
    log "Please configure .env file or export variables"
    exit 1
fi

# Set paper trading mode (safety first)
export PAPER_TRADING="${PAPER_TRADING:-true}"
export DAILY_INVESTMENT="${DAILY_INVESTMENT:-50}"

log "Configuration:"
log "  PAPER_TRADING: $PAPER_TRADING"
log "  DAILY_INVESTMENT: $DAILY_INVESTMENT"

# Run the trading script
log "Executing autonomous_trader.py..."
python3 "$PROJECT_ROOT/scripts/autonomous_trader.py" 2>&1 | tee -a "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}

if [ $EXIT_CODE -eq 0 ]; then
    log "✅ Trading completed successfully"
else
    log "❌ Trading failed with exit code: $EXIT_CODE"
fi

# Update local heartbeat to show cron ran
mkdir -p "$PROJECT_ROOT/data"
cat > "$PROJECT_ROOT/data/local_cron_heartbeat.json" << EOF
{
    "last_run": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "source": "local_cron",
    "exit_code": $EXIT_CODE,
    "hostname": "$(hostname)"
}
EOF

log "=========================================="
log "LOCAL TRADING CRON - Completed"
log "=========================================="

exit $EXIT_CODE
