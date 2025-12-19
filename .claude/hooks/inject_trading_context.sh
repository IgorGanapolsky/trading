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
# Fixed: Use jq .[-1] to get last array element instead of tail -1 which returns "]"
if [[ -f "$PERF_LOG" ]]; then
    PERF_DATE=$(jq -r '.[-1].date // ""' "$PERF_LOG" 2>/dev/null || echo "")
    CURRENT_EQUITY=$(jq -r '.[-1].equity // "N/A"' "$PERF_LOG" 2>/dev/null || echo "N/A")
    TOTAL_PL=$(jq -r '.[-1].pl // "N/A"' "$PERF_LOG" 2>/dev/null || echo "N/A")
    TOTAL_PL_PCT_RAW=$(jq -r '.[-1].pl_pct // "N/A"' "$PERF_LOG" 2>/dev/null || echo "N/A")
    # pl_pct is already a percentage (e.g., -0.09 means -0.09%), just format it
    if [[ "$TOTAL_PL_PCT_RAW" != "N/A" ]]; then
        TOTAL_PL_PCT=$(printf "%.2f" "$TOTAL_PL_PCT_RAW" 2>/dev/null || echo "$TOTAL_PL_PCT_RAW")
    else
        TOTAL_PL_PCT="N/A"
    fi
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

# Check market status - CRITICAL: Crypto trades 24/7/365!
CURRENT_TIME=$(TZ=America/New_York date +%H:%M)
CURRENT_DAY_OF_WEEK=$(date +%u)  # 1=Monday, 7=Sunday

# Crypto is ALWAYS open - this is Critical Rule #5
CRYPTO_STATUS="OPEN 24/7"

if [[ $CURRENT_DAY_OF_WEEK -ge 1 && $CURRENT_DAY_OF_WEEK -le 5 ]]; then
    # Weekday
    if [[ "$CURRENT_TIME" > "09:30" && "$CURRENT_TIME" < "16:00" ]]; then
        EQUITY_STATUS="OPEN"
    else
        EQUITY_STATUS="CLOSED (opens 9:30 AM ET)"
    fi
else
    # Weekend - equities closed but CRYPTO IS ALWAYS OPEN
    EQUITY_STATUS="CLOSED (weekend)"
fi

# Combined status showing both markets
MARKET_STATUS="Equities: $EQUITY_STATUS | Crypto: $CRYPTO_STATUS"

# Next automated trade time - MUST be a weekday (Mon-Fri)
# Fixed Dec 19, 2025: Was showing Saturday as next trade date
get_next_trading_day() {
    local dow=$(date +%u)  # 1=Mon, 7=Sun
    local days_to_add=1

    # If Friday (5), next trade is Monday (+3 days)
    if [[ $dow -eq 5 ]]; then
        days_to_add=3
    # If Saturday (6), next trade is Monday (+2 days)
    elif [[ $dow -eq 6 ]]; then
        days_to_add=2
    # If Sunday (7), next trade is Monday (+1 day)
    elif [[ $dow -eq 7 ]]; then
        days_to_add=1
    fi

    # Try macOS date first (-v), then GNU date (-d)
    TZ=America/New_York date -v +${days_to_add}d '+%b %d, 9:35 AM ET' 2>/dev/null || \
    date -d "+${days_to_add} days" '+%b %d, 9:35 AM ET' 2>/dev/null || \
    echo "Next weekday 9:35 AM ET"
}
NEXT_TRADE=$(get_next_trading_day)

# Get backtest status from actual results if available
BACKTEST_SUMMARY="$CLAUDE_PROJECT_DIR/data/backtests/latest_summary.json"
if [[ -f "$BACKTEST_SUMMARY" ]]; then
    PASSES=$(jq -r '.aggregate_metrics.passes // 0' "$BACKTEST_SUMMARY" 2>/dev/null || echo "0")
    TOTAL=$(jq -r '.aggregate_metrics.total // 13' "$BACKTEST_SUMMARY" 2>/dev/null || echo "13")
    MIN_SHARPE=$(jq -r '.aggregate_metrics.min_sharpe_ratio // "N/A"' "$BACKTEST_SUMMARY" 2>/dev/null || echo "N/A")
    if [[ "$MIN_SHARPE" != "N/A" ]]; then
        SHARPE_NOTE="Sharpe: $MIN_SHARPE"
    else
        SHARPE_NOTE="Sharpe: negative"
    fi
    BACKTEST_STATUS="$PASSES/$TOTAL scenarios pass ($SHARPE_NOTE)"
else
    BACKTEST_STATUS="Not run yet (run scripts/run_backtest_matrix.py)"
fi

# Output context (this will be added to the user's prompt)
cat <<EOF
[TRADING CONTEXT]
Portfolio: \$$CURRENT_EQUITY | P/L: \$$TOTAL_PL ($TOTAL_PL_PCT%) | Day: $CURRENT_DAY/90
Win Rate: $WIN_RATE% (live) | Backtest: $BACKTEST_STATUS
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

# Budget awareness (BATS framework)
BUDGET_FILE="$CLAUDE_PROJECT_DIR/data/budget_tracker.json"
if [[ -f "$BUDGET_FILE" ]]; then
    BUDGET_SPENT=$(jq -r '.spent_this_month // 0' "$BUDGET_FILE" 2>/dev/null || echo "0")
    BUDGET_REMAINING=$(echo "100 - $BUDGET_SPENT" | bc -l 2>/dev/null || echo "100")
    echo "Budget: \$${BUDGET_REMAINING%.*} remaining of \$100/mo"
fi

exit 0
