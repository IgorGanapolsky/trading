#!/bin/bash
#
# Claude Code UserPromptSubmit Hook - Inject Trading Context
#
# This hook runs when the user submits a prompt, injecting current
# trading system status, portfolio metrics, and market information
# to provide Claude with full context for better decision-making.
#
# UPDATED Dec 12, 2025 (LL-018, LL-019): Added stale data detection
#

set -euo pipefail

# Path to data files
STATE_FILE="$CLAUDE_PROJECT_DIR/data/system_state.json"
PERF_LOG="$CLAUDE_PROJECT_DIR/data/performance_log.json"
TODAY=$(date +%Y-%m-%d)
TRADE_FILE="$CLAUDE_PROJECT_DIR/data/trades_${TODAY}.json"

# Check if system state exists
if [[ ! -f "$STATE_FILE" ]]; then
    echo "[TRADING CONTEXT: System not yet initialized]" >&1
    exit 0
fi

# Get most recent data from performance_log.json (more reliable than system_state)
if [[ -f "$PERF_LOG" ]]; then
    PERF_DATE=$(tail -1 "$PERF_LOG" | jq -r '.date // ""' 2>/dev/null || echo "")
    CURRENT_EQUITY=$(tail -1 "$PERF_LOG" | jq -r '.equity // "N/A"' 2>/dev/null || echo "N/A")
    TOTAL_PL=$(tail -1 "$PERF_LOG" | jq -r '.pl // "N/A"' 2>/dev/null || echo "N/A")
    TOTAL_PL_PCT=$(tail -1 "$PERF_LOG" | jq -r '.pl_pct // "N/A"' 2>/dev/null || echo "N/A")
else
    PERF_DATE=""
    CURRENT_EQUITY=$(jq -r '.account.current_equity // "N/A"' "$STATE_FILE")
    TOTAL_PL=$(jq -r '.account.total_pl // "N/A"' "$STATE_FILE")
    TOTAL_PL_PCT=$(jq -r '.account.total_pl_pct // "N/A"' "$STATE_FILE")
fi

CURRENT_DAY=$(jq -r '.challenge.current_day // "N/A"' "$STATE_FILE")
WIN_RATE=$(jq -r '.performance.win_rate // "N/A"' "$STATE_FILE")

# Check data freshness and warn if stale
STALE_WARNING=""
if [[ -n "$PERF_DATE" && "$PERF_DATE" != "$TODAY" ]]; then
    DAYS_OLD=$(( ($(date +%s) - $(date -d "$PERF_DATE" +%s 2>/dev/null || echo 0)) / 86400 ))
    if [[ $DAYS_OLD -gt 0 ]]; then
        STALE_WARNING="⚠️ DATA STALE: Last update $PERF_DATE ($DAYS_OLD days ago)"
    fi
fi

# Check if today's trade file exists
TRADE_WARNING=""
if [[ ! -f "$TRADE_FILE" ]]; then
    TRADE_WARNING="⚠️ NO TRADES TODAY"
fi

# Check if markets are open (Mon-Fri, 9:30 AM - 4:00 PM ET)
CURRENT_TIME=$(TZ=America/New_York date +%H:%M)
CURRENT_DAY_OF_WEEK=$(date +%u)  # 1=Monday, 7=Sunday

if [[ $CURRENT_DAY_OF_WEEK -ge 1 && $CURRENT_DAY_OF_WEEK -le 5 ]]; then
    # Weekday
    if [[ "$CURRENT_TIME" > "09:30" && "$CURRENT_TIME" < "16:00" ]]; then
        MARKET_STATUS="OPEN"
    else
        MARKET_STATUS="CLOSED (opens 9:30 AM ET)"
    fi
else
    # Weekend
    MARKET_STATUS="CLOSED (weekend)"
fi

# Next automated trade time
NEXT_TRADE=$(TZ=America/New_York date -v +1d '+%b %d, 9:35 AM ET' 2>/dev/null || date -d '+1 day' '+%b %d, 9:35 AM ET' 2>/dev/null || echo "Tomorrow 9:35 AM ET")

# Output context (this will be added to the user's prompt)
cat <<EOF
[TRADING CONTEXT]
Portfolio: \$$CURRENT_EQUITY | P/L: \$$TOTAL_PL ($TOTAL_PL_PCT%) | Day: $CURRENT_DAY/90
Win Rate: $WIN_RATE% (live) | Backtest: 62.2% win rate, 2.18 Sharpe
Next Trade: $NEXT_TRADE
Markets: $MARKET_STATUS
EOF

# Output warnings if any
if [[ -n "$STALE_WARNING" ]]; then
    echo "$STALE_WARNING"
fi
if [[ -n "$TRADE_WARNING" ]]; then
    echo "$TRADE_WARNING"
fi

exit 0
