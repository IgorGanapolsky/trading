#!/bin/bash
#
# Claude Code UserPromptSubmit Hook - Inject Trading Context
#
# This hook runs when the user submits a prompt, injecting current
# trading system status, portfolio metrics, and market information
# to provide Claude with full context for better decision-making.
#
# UPDATED Dec 12, 2025 (LL-018, LL-019): Added stale data detection
# UPDATED Dec 19, 2025: LIVE Alpaca API fetch - no more stale data!
# UPDATED Dec 19, 2025: Auto-load credentials from .env.local
# UPDATED Dec 19, 2025: Added EXPLICIT calendar awareness (day of week)
#

set -euo pipefail

# ============================================================================
# CALENDAR AWARENESS - Know what day it is!
# This is CRITICAL for trading decisions. Markets closed Sat/Sun AND holidays.
# ============================================================================
DAY_OF_WEEK=$(TZ=America/New_York date +%A)      # Monday, Tuesday, etc.
DAY_NUM=$(TZ=America/New_York date +%u)          # 1=Monday, 7=Sunday
FULL_DATE=$(TZ=America/New_York date '+%A, %B %d, %Y')  # Friday, December 19, 2025
TODAY_DATE=$(TZ=America/New_York date +%Y-%m-%d)  # 2026-01-19 format for holiday check
IS_WEEKEND="false"
IS_HOLIDAY="false"
HOLIDAY_NAME=""

if [[ $DAY_NUM -ge 6 ]]; then
    IS_WEEKEND="true"
fi

# ============================================================================
# US MARKET HOLIDAYS 2025-2026 (NYSE/NASDAQ closed)
# CRITICAL: Markets are CLOSED on these dates - DO NOT TRADE
# Updated Jan 19, 2026 after MLK Day bug discovery
# ============================================================================
declare -A US_MARKET_HOLIDAYS=(
    # 2025 Holidays
    ["2025-01-01"]="New Year's Day"
    ["2025-01-20"]="Martin Luther King Jr. Day"
    ["2025-02-17"]="Presidents Day"
    ["2025-04-18"]="Good Friday"
    ["2025-05-26"]="Memorial Day"
    ["2025-06-19"]="Juneteenth"
    ["2025-07-04"]="Independence Day"
    ["2025-09-01"]="Labor Day"
    ["2025-11-27"]="Thanksgiving Day"
    ["2025-12-25"]="Christmas Day"
    # 2026 Holidays
    ["2026-01-01"]="New Year's Day"
    ["2026-01-19"]="Martin Luther King Jr. Day"
    ["2026-02-16"]="Presidents Day"
    ["2026-04-03"]="Good Friday"
    ["2026-05-25"]="Memorial Day"
    ["2026-06-19"]="Juneteenth"
    ["2026-07-03"]="Independence Day (observed)"
    ["2026-09-07"]="Labor Day"
    ["2026-11-26"]="Thanksgiving Day"
    ["2026-12-25"]="Christmas Day"
)

# Check if today is a US market holiday
if [[ -v "US_MARKET_HOLIDAYS[$TODAY_DATE]" ]]; then
    IS_HOLIDAY="true"
    HOLIDAY_NAME="${US_MARKET_HOLIDAYS[$TODAY_DATE]}"
fi

# ============================================================================
# LOAD LOCAL CREDENTIALS (Dec 19, 2025 fix for persistence)
# Source .env.local if it exists to get Alpaca keys
# ============================================================================
if [[ -f "$CLAUDE_PROJECT_DIR/.env.local" ]]; then
    source "$CLAUDE_PROJECT_DIR/.env.local"
fi

# Path to data files
STATE_FILE="$CLAUDE_PROJECT_DIR/data/system_state.json"
PERF_LOG="$CLAUDE_PROJECT_DIR/data/performance_log.json"
# CRITICAL: Use ET timezone for TODAY - server runs in UTC but trading is ET
TODAY=$(TZ=America/New_York date +%Y-%m-%d)
TRADE_FILE="$CLAUDE_PROJECT_DIR/data/trades_${TODAY}.json"

# Check if system state exists
if [[ ! -f "$STATE_FILE" ]]; then
    echo "[TRADING CONTEXT: System not yet initialized]" >&1
    exit 0
fi

# ============================================================================
# LIVE ALPACA DATA FETCH (Dec 19, 2025 fix)
# Try to get REAL data from Alpaca API first, fall back to local files
# ============================================================================
# PRIORITY: Use $5K paper account keys first (per CLAUDE.md directive)
ALPACA_API_KEY="${ALPACA_PAPER_TRADING_5K_API_KEY:-${ALPACA_API_KEY:-}}"
ALPACA_SECRET_KEY="${ALPACA_PAPER_TRADING_5K_API_SECRET:-${ALPACA_SECRET_KEY:-}}"
LIVE_DATA="false"
PERF_DATE=""

if [[ -n "$ALPACA_API_KEY" && -n "$ALPACA_SECRET_KEY" ]]; then
    # Try to fetch live data from Alpaca
    ALPACA_RESPONSE=$(curl -s --max-time 5 \
        -H "APCA-API-KEY-ID: $ALPACA_API_KEY" \
        -H "APCA-API-SECRET-KEY: $ALPACA_SECRET_KEY" \
        "https://paper-api.alpaca.markets/v2/account" 2>/dev/null || echo "")

    if [[ -n "$ALPACA_RESPONSE" && "$ALPACA_RESPONSE" != *"error"* && "$ALPACA_RESPONSE" != *"forbidden"* ]]; then
        CURRENT_EQUITY=$(echo "$ALPACA_RESPONSE" | jq -r '.equity // "N/A"' 2>/dev/null || echo "N/A")
        LAST_EQUITY=$(echo "$ALPACA_RESPONSE" | jq -r '.last_equity // "100000"' 2>/dev/null || echo "100000")

        if [[ "$CURRENT_EQUITY" != "N/A" && "$CURRENT_EQUITY" != "null" ]]; then
            # Calculate P/L from Alpaca data
            TOTAL_PL=$(echo "$CURRENT_EQUITY - 100000" | bc -l 2>/dev/null || echo "0")
            TOTAL_PL_PCT=$(echo "scale=2; ($CURRENT_EQUITY - 100000) / 1000" | bc -l 2>/dev/null || echo "0")
            PERF_DATE="$TODAY"
            LIVE_DATA="true"
        fi
    fi
fi

# Fall back to local files if live fetch failed
if [[ "$LIVE_DATA" == "false" ]]; then
    # PRIORITY: Use system_state.json (paper account) - per CLAUDE.md directive
    # performance_log.json tracks brokerage ($60), system_state tracks paper ($5K)
    if [[ -f "$STATE_FILE" ]]; then
        # Check meta.last_updated first (sync-alpaca-status), then fallback to last_updated
        PERF_DATE=$(jq -r '.meta.last_updated // .last_updated // ""' "$STATE_FILE" 2>/dev/null | cut -d'T' -f1 || echo "")
        CURRENT_EQUITY=$(jq -r '.paper_account.equity // .portfolio.equity // "N/A"' "$STATE_FILE" 2>/dev/null || echo "N/A")
        TOTAL_PL=$(jq -r '.paper_account.total_pl // "N/A"' "$STATE_FILE" 2>/dev/null || echo "N/A")
        TOTAL_PL_PCT_RAW=$(jq -r '.paper_account.total_pl_pct // "N/A"' "$STATE_FILE" 2>/dev/null || echo "N/A")
        if [[ "$TOTAL_PL_PCT_RAW" != "N/A" ]]; then
            TOTAL_PL_PCT=$(printf "%.2f" "$TOTAL_PL_PCT_RAW" 2>/dev/null || echo "$TOTAL_PL_PCT_RAW")
        else
            TOTAL_PL_PCT="N/A"
        fi
    elif [[ -f "$PERF_LOG" ]]; then
        # Secondary fallback to performance_log (brokerage account)
        PERF_DATE=$(jq -r '.[-1].date // ""' "$PERF_LOG" 2>/dev/null || echo "")
        CURRENT_EQUITY=$(jq -r '.[-1].equity // "N/A"' "$PERF_LOG" 2>/dev/null || echo "N/A")
        TOTAL_PL=$(jq -r '.[-1].pl // "N/A"' "$PERF_LOG" 2>/dev/null || echo "N/A")
        TOTAL_PL_PCT_RAW=$(jq -r '.[-1].pl_pct // "N/A"' "$PERF_LOG" 2>/dev/null || echo "N/A")
        if [[ "$TOTAL_PL_PCT_RAW" != "N/A" ]]; then
            TOTAL_PL_PCT=$(printf "%.2f" "$TOTAL_PL_PCT_RAW" 2>/dev/null || echo "$TOTAL_PL_PCT_RAW")
        else
            TOTAL_PL_PCT="N/A"
        fi
    else
        PERF_DATE=""
        CURRENT_EQUITY="N/A"
        TOTAL_PL="N/A"
        TOTAL_PL_PCT="N/A"
    fi
fi

CURRENT_DAY=$(jq -r '.challenge.current_day // "N/A"' "$STATE_FILE")
# FIXED Jan 9, 2026: Read from paper_account (current) instead of performance (stale pre-reset data)
WIN_RATE=$(jq -r '.paper_account.win_rate // "N/A"' "$STATE_FILE")
# paper_account doesn't track avg_return per trade yet - calculate from total_pl_pct if needed
AVG_RETURN=$(jq -r '.paper_account.total_pl_pct // "0"' "$STATE_FILE")
WIN_RATE_SAMPLE=$(jq -r '.paper_account.win_rate_sample_size // "N/A"' "$STATE_FILE")

# HONEST REPORTING (LL-118): Win rate without avg_return is MISLEADING
# If avg_return is negative, the win rate is lying to us
WIN_RATE_DISPLAY="$WIN_RATE"
if [[ "$AVG_RETURN" != "N/A" ]]; then
    AVG_RETURN_ROUNDED=$(printf "%.1f" "$AVG_RETURN" 2>/dev/null || echo "$AVG_RETURN")
    if (( $(echo "$AVG_RETURN < 0" | bc -l 2>/dev/null || echo 0) )); then
        WIN_RATE_DISPLAY="$WIN_RATE (MISLEADING - avg return: ${AVG_RETURN_ROUNDED}%)"
    fi
fi

# Check data freshness and warn if stale
STALE_WARNING=""
DATA_SOURCE=""
if [[ "$LIVE_DATA" == "true" ]]; then
    DATA_SOURCE="✅ LIVE from Alpaca"
elif [[ -n "$PERF_DATE" && "$PERF_DATE" != "$TODAY" ]]; then
    # Use ET timezone for date calculations
    DAYS_OLD=$(( ($(TZ=America/New_York date +%s) - $(TZ=America/New_York date -d "$PERF_DATE" +%s 2>/dev/null || echo 0)) / 86400 ))
    if [[ $DAYS_OLD -gt 0 ]]; then
        STALE_WARNING="⚠️ DATA STALE: Last update $PERF_DATE ($DAYS_OLD days ago)"
        DATA_SOURCE="📁 Local files (stale)"
    fi
else
    DATA_SOURCE="📁 Local files"
fi

# Check if today's trade file exists
TRADE_WARNING=""
if [[ ! -f "$TRADE_FILE" ]]; then
    TRADE_WARNING="⚠️ NO TRADES TODAY"
fi

# Check market status - US Equities ONLY (we don't trade crypto)
# UPDATED Jan 5, 2026: Fixed ambiguous output that caused Claude to misinterpret market status
# UPDATED Jan 19, 2026: Added US market holiday detection (MLK Day bug fix)
# FIXED Jan 20, 2026: Use %-H (no leading zero) to avoid bash octal interpretation bug
# BUG: "09" with leading zero was interpreted as octal, causing -lt/-eq to fail silently
# See LL-074: Hook output must be EXPLICIT about market state
CURRENT_TIME=$(TZ=America/New_York date +%H:%M)
CURRENT_HOUR=$(TZ=America/New_York date +%-H)  # %-H removes leading zero (9 not 09)

TRADING_ALLOWED="NO"
MARKET_STATE=""
MARKET_REASON=""

# PRIORITY CHECK: Holidays override everything (even weekdays)
if [[ "$IS_HOLIDAY" == "true" ]]; then
    MARKET_STATE="HOLIDAY_CLOSED"
    MARKET_REASON="🎉 $HOLIDAY_NAME - US markets CLOSED. Next open: Next trading day 9:30 AM ET"
    TRADING_ALLOWED="NO"
elif [[ $DAY_NUM -ge 1 && $DAY_NUM -le 5 ]]; then
    # Weekday (Mon-Fri) - but NOT a holiday
    if [[ "$CURRENT_TIME" > "09:30" && "$CURRENT_TIME" < "16:00" ]]; then
        MARKET_STATE="OPEN"
        MARKET_REASON="Regular trading hours (9:30 AM - 4:00 PM ET)"
        TRADING_ALLOWED="YES"
    elif [[ "$CURRENT_HOUR" -lt 9 || ("$CURRENT_HOUR" -eq 9 && "$CURRENT_TIME" < "09:30") ]]; then
        MARKET_STATE="PRE_MARKET"
        MARKET_REASON="Market opens TODAY at 9:30 AM ET (currently $CURRENT_TIME ET)"
        TRADING_ALLOWED="NO"
    else
        MARKET_STATE="POST_MARKET"
        MARKET_REASON="Market closed for today at 4:00 PM ET"
        TRADING_ALLOWED="NO"
    fi
else
    # Weekend (Sat/Sun) - NO TRADING
    MARKET_STATE="WEEKEND_CLOSED"
    MARKET_REASON="Markets closed Sat/Sun. Next open: Monday 9:30 AM ET"
    TRADING_ALLOWED="NO"
fi

# Build unambiguous status string
MARKET_STATUS="$MARKET_STATE - $MARKET_REASON [TRADING_ALLOWED=$TRADING_ALLOWED]"

# Next automated trade time - MUST be a weekday (Mon-Fri) AND not a holiday
# Fixed Dec 30, 2025: Was showing tomorrow even on trading days before market close
# Fixed Jan 19, 2026: Now checks for holidays (MLK Day bug)
get_next_trading_day() {
    local dow=$(TZ=America/New_York date +%u)  # 1=Mon, 7=Sun
    local hour=$(TZ=America/New_York date +%-H)  # Current hour in ET (no leading zero)
    local days_to_add=0

    # PRIORITY: If today is a holiday, skip to tomorrow
    if [[ "$IS_HOLIDAY" == "true" ]]; then
        days_to_add=1
        # If Monday holiday, next trading day is Tuesday (unless Tuesday is also a holiday)
    # If it's a weekday (Mon-Fri, dow 1-5) and NOT a holiday
    elif [[ $dow -ge 1 && $dow -le 5 ]]; then
        # If before market close (4 PM ET = 16:00), trade is TODAY
        if [[ 10#$hour -lt 16 ]]; then
            days_to_add=0
        else
            # After market close - next trade is tomorrow (or Monday if Friday)
            if [[ $dow -eq 5 ]]; then
                days_to_add=3  # Friday after close -> Monday
            else
                days_to_add=1  # Mon-Thu after close -> next day
            fi
        fi
    # Saturday (6) -> Monday (+2)
    elif [[ $dow -eq 6 ]]; then
        days_to_add=2
    # Sunday (7) -> Monday (+1)
    elif [[ $dow -eq 7 ]]; then
        days_to_add=1
    fi

    if [[ $days_to_add -eq 0 ]]; then
        echo "TODAY $(TZ=America/New_York date '+%b %d'), 9:35 AM ET"
    else
        # Try macOS date first (-v), then GNU date (-d)
        TZ=America/New_York date -v +${days_to_add}d '+%b %d, 9:35 AM ET' 2>/dev/null || \
        TZ=America/New_York date -d "+${days_to_add} days" '+%b %d, 9:35 AM ET' 2>/dev/null || \
        echo "Next weekday 9:35 AM ET"
    fi
}
NEXT_TRADE=$(get_next_trading_day)

# Get backtest status from actual results if available
BACKTEST_SUMMARY="$CLAUDE_PROJECT_DIR/data/backtests/latest_summary.json"
if [[ -f "$BACKTEST_SUMMARY" ]]; then
    PASSES=$(jq -r '.aggregate_metrics.passes // 0' "$BACKTEST_SUMMARY" 2>/dev/null || echo "0")
    TOTAL=$(jq -r '.scenario_count // 19' "$BACKTEST_SUMMARY" 2>/dev/null || echo "19")
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
# CALENDAR INFO FIRST - so Claude always knows what day it is
cat <<EOF
[TRADING CONTEXT] $DATA_SOURCE
EOF

# AGGRESSIVE CALENDAR WARNING - Claude keeps forgetting day of week
echo "═══════════════════════════════════════════════════════════"
echo "📅 TODAY: $FULL_DATE"
if [[ "$DAY_OF_WEEK" == "Friday" ]]; then
    echo "⚠️  TOMORROW IS SATURDAY - NO TRADING SATURDAY/SUNDAY"
    echo "⚠️  NEXT TRADING DAY: MONDAY"
elif [[ "$IS_WEEKEND" == "true" ]]; then
    echo "🚫 WEEKEND - MARKETS CLOSED - NO TRADING TODAY"
fi
echo "═══════════════════════════════════════════════════════════"

cat <<EOF
Portfolio: \$$CURRENT_EQUITY | P/L: \$$TOTAL_PL ($TOTAL_PL_PCT%) | Day: $CURRENT_DAY/90
Win Rate: $WIN_RATE_DISPLAY% (n=$WIN_RATE_SAMPLE) | Backtest: $BACKTEST_STATUS
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

# Session start reminder - Check deferred items
DEFERRED_COUNT=$(grep -l "Month 3\|#deferred" "$CLAUDE_PROJECT_DIR/rag_knowledge/lessons_learned/"*.md 2>/dev/null | wc -l || echo "0")
if [[ "$DEFERRED_COUNT" -gt 0 ]]; then
    echo "📌 Deferred items: $DEFERRED_COUNT (see .claude/SESSION_START_CHECKLIST.md)"
fi

# Check for pending dry-run requirement (Gap fix Jan 7, 2026)
DRYRUN_STATE="$CLAUDE_PROJECT_DIR/data/dryrun_state.json"
if [[ -f "$DRYRUN_STATE" ]]; then
    DRYRUN_REQUIRED=$(jq -r '.dryrun_required // false' "$DRYRUN_STATE" 2>/dev/null || echo "false")
    if [[ "$DRYRUN_REQUIRED" == "true" ]]; then
        LAST_MERGE=$(jq -r '.last_merge // "unknown"' "$DRYRUN_STATE" 2>/dev/null || echo "unknown")
        echo "🚨 DRY-RUN REQUIRED: Merge detected at $LAST_MERGE"
        echo "   Run: python3 scripts/system_health_check.py --dry-run"
    fi
fi

# CEO Directive (Jan 15, 2026): Session start verification reminder
# Verify Alpaca (truth) vs Dashboard vs Dialogflow on session start
echo "💡 Verify status: python3 scripts/session_start_verification.py"

exit 0
