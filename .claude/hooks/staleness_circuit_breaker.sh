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

    last_updated_str = state.get('meta', {}).get('last_updated', '')
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
    echo "🚨 STALENESS CIRCUIT BREAKER ACTIVATED 🚨"
    echo "════════════════════════════════════════════════════════════"
    echo ""
    echo "State file age: ${LAST_UPDATED} hours"
    echo "Maximum allowed: ${MAX_STALENESS_HOURS} hours"
    echo ""
    echo "TRADING BLOCKED: Cannot make decisions on stale data."
    echo ""
    echo "To proceed:"
    echo "  1. Update state from Alpaca: python3 scripts/sync_alpaca_state.py"
    echo "  2. Or manually verify and update: data/system_state.json"
    echo ""
    echo "This circuit breaker exists because of incident LL-058:"
    echo "  'Dec 23 stale data lying incident - 9 SPY trades executed"
    echo "   but local data showed NO TRADES TODAY'"
    echo "════════════════════════════════════════════════════════════"
    exit 1
fi

echo "✅ State freshness OK: ${LAST_UPDATED} hours old (max: ${MAX_STALENESS_HOURS}h)"
