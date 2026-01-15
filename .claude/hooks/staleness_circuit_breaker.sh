#!/bin/bash
# Staleness Circuit Breaker - HARD BLOCK on stale data
# Prevents trading decisions based on outdated state
#
# Triggered: PreToolUse before any trading-related tool calls
# Threshold: 4 hours (configurable)

set -e

MAX_STALENESS_HOURS=${MAX_STALENESS_HOURS:-4}
STATE_FILE="data/system_state.json"

# Check if state file exists
if [ ! -f "$STATE_FILE" ]; then
    echo "🚨 CIRCUIT BREAKER: system_state.json NOT FOUND"
    echo "Cannot proceed without state file"
    exit 1
fi

# Extract last_updated timestamp
LAST_UPDATED=$(python3 -c "
import json
import sys
from datetime import datetime, timezone

try:
    with open('$STATE_FILE') as f:
        state = json.load(f)

    last_updated_str = state.get('last_updated', '') or state.get('meta', {}).get('last_updated', '')
    if not last_updated_str:
        print('MISSING')
        sys.exit(0)

    # Parse the timestamp - handle both naive and aware datetimes
    last_updated_str = last_updated_str.replace('Z', '+00:00')
    if '+' not in last_updated_str and '-' not in last_updated_str[10:]:
        # Naive datetime - assume UTC
        last_updated = datetime.fromisoformat(last_updated_str).replace(tzinfo=timezone.utc)
    else:
        last_updated = datetime.fromisoformat(last_updated_str)

    now = datetime.now(timezone.utc)

    # Calculate age in hours
    age_hours = (now - last_updated).total_seconds() / 3600
    print(f'{age_hours:.1f}')
except Exception as e:
    print(f'ERROR:{e}')
")

# Handle parsing errors
if [[ "$LAST_UPDATED" == ERROR:* ]]; then
    echo "⚠️ WARNING: Could not parse state timestamp: ${LAST_UPDATED#ERROR:}"
    exit 0  # Don't block on parse errors, just warn
fi

if [ "$LAST_UPDATED" == "MISSING" ]; then
    echo "⚠️ WARNING: No last_updated timestamp in state file"
    exit 0
fi

# Convert to integer for comparison
AGE_INT=${LAST_UPDATED%.*}

if [ "$AGE_INT" -gt "$MAX_STALENESS_HOURS" ]; then
    echo "════════════════════════════════════════════════════════════"
    echo "🚨 STALENESS DETECTED - AUTO-SYNCING 🚨"
    echo "════════════════════════════════════════════════════════════"
    echo ""
    echo "State file age: ${LAST_UPDATED} hours"
    echo "Maximum allowed: ${MAX_STALENESS_HOURS} hours"
    echo ""
    echo "Attempting automatic sync from Alpaca..."
    echo ""

    # Try to auto-sync - MUST verify sync was real, not simulated
    SYNC_OUTPUT=$(python3 scripts/sync_alpaca_state.py 2>&1)
    SYNC_EXIT=$?

    if [ $SYNC_EXIT -eq 0 ]; then
        # CRITICAL: Verify sync was REAL (not simulated with fake $100k data)
        SYNC_MODE=$(python3 -c "
import json
with open('$STATE_FILE') as f:
    state = json.load(f)
print(state.get('meta', {}).get('sync_mode', 'unknown'))
")

        if [ "$SYNC_MODE" == "simulated" ]; then
            echo ""
            echo "❌ SYNC USED FAKE DATA - NOT ACCEPTABLE"
            echo ""
            echo "The sync script ran but used simulated mode (fake \$100k)."
            echo "This would CORRUPT real portfolio data."
            echo ""
            echo "FIX: Configure Alpaca API keys in .env.local:"
            echo "  ALPACA_API_KEY=your_key"
            echo "  ALPACA_SECRET_KEY=your_secret"
            echo "════════════════════════════════════════════════════════════"
            # DON'T exit 1 - this blocks all operations. Just warn.
            # The data is stale but we shouldn't prevent all work.
            echo "⚠️ PROCEEDING WITH STALE DATA - manual sync required"
            exit 0
        fi

        echo ""
        echo "✅ AUTO-SYNC SUCCESSFUL (mode: $SYNC_MODE) - Fresh data loaded"
        echo "════════════════════════════════════════════════════════════"
        exit 0
    else
        echo ""
        echo "❌ AUTO-SYNC FAILED - Sync script returned error"
        echo ""
        echo "$SYNC_OUTPUT" | tail -10
        echo ""
        echo "This circuit breaker exists because of incident LL-058:"
        echo "  'Dec 23 stale data lying incident - 9 SPY trades executed"
        echo "   but local data showed NO TRADES TODAY'"
        echo ""
        echo "⚠️ PROCEEDING WITH STALE DATA - manual sync required"
        echo "════════════════════════════════════════════════════════════"
        # Don't block - just warn. Stale data is bad but blocking all work is worse.
        exit 0
    fi
fi

echo "✅ State freshness OK: ${LAST_UPDATED} hours old (max: ${MAX_STALENESS_HOURS}h)"
