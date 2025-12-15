#!/bin/bash
#
# Claude Code SessionStart Hook - Load Trading State
#
# This hook runs at the start of each Claude Code session to load
# the current trading system state and provide a summary.
#

set -euo pipefail

# Path to system state file
STATE_FILE="$CLAUDE_PROJECT_DIR/data/system_state.json"

# Check if system state exists
if [[ ! -f "$STATE_FILE" ]]; then
    echo "📊 Trading system not yet initialized" >&2
    exit 0
fi

# Extract key information
CURRENT_EQUITY=$(jq -r '.account.current_equity // "N/A"' "$STATE_FILE")
TOTAL_PL=$(jq -r '.account.total_pl // "N/A"' "$STATE_FILE")
CURRENT_DAY=$(jq -r '.challenge.current_day // "N/A"' "$STATE_FILE")
LAST_UPDATED=$(jq -r '.meta.last_updated // "N/A"' "$STATE_FILE")

# Check launchd automation status
if launchctl list | grep -q "com.trading.autonomous"; then
    AUTOMATION_STATUS="✅ Running"
else
    AUTOMATION_STATUS="❌ Not running"
fi

# Output session summary
cat <<EOF >&2

================================================================================
🤖 TRADING SYSTEM SESSION START
================================================================================
Portfolio: \$$CURRENT_EQUITY | P/L: \$$TOTAL_PL | Day: $CURRENT_DAY/90
Automation: $AUTOMATION_STATUS
Last Updated: $LAST_UPDATED
Backtest Reality: 0/13 pass | Sharpe: -7 to -2086 | NO EDGE YET
================================================================================

EOF

exit 0
