#!/bin/bash
#
# Claude Code UserPromptSubmit Hook - Inject Trading Context
#
# This hook runs when the user submits a prompt, injecting current
# trading system status, portfolio metrics, and market information
# to provide Claude with full context for better decision-making.
#

set -euo pipefail

# Path to system state file
STATE_FILE="$CLAUDE_PROJECT_DIR/data/system_state.json"

# Check if system state exists
if [[ ! -f "$STATE_FILE" ]]; then
    # No state yet, system hasn't started trading
    echo "[TRADING CONTEXT: System not yet initialized]" >&1
    exit 0
fi

# Extract key metrics from system state
CURRENT_EQUITY=$(jq -r '.account.current_equity // "N/A"' "$STATE_FILE")
TOTAL_PL=$(jq -r '.account.total_pl // "N/A"' "$STATE_FILE")
TOTAL_PL_PCT=$(jq -r '.account.total_pl_pct // "N/A"' "$STATE_FILE")
CURRENT_DAY=$(jq -r '.challenge.current_day // "N/A"' "$STATE_FILE")
WIN_RATE=$(jq -r '.performance.win_rate // "N/A"' "$STATE_FILE")

# Extract ACTUAL backtest metrics (not hardcoded lies)
BACKTEST_WIN_RATE=$(jq -r '.backtest_reality.daily_win_rate_range // "38-52"' "$STATE_FILE")
BACKTEST_SHARPE=$(jq -r '.backtest_reality.sharpe_ratio_range // "negative"' "$STATE_FILE")
BACKTEST_STATUS=$(jq -r '.backtest_reality.status // "NEEDS_IMPROVEMENT"' "$STATE_FILE")

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
Win Rate: $WIN_RATE% (live) | Backtest: $BACKTEST_WIN_RATE% win rate, Sharpe: $BACKTEST_SHARPE
Status: $BACKTEST_STATUS | Next Trade: $NEXT_TRADE
Markets: $MARKET_STATUS
EOF

exit 0
