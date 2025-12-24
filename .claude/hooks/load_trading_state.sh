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
if launchctl list 2>/dev/null | grep -q "com.trading.autonomous"; then
    AUTOMATION_STATUS="✅ Running"
else
    AUTOMATION_STATUS="⏸️  Manual mode"
fi

# Check feedback stats
FEEDBACK_STATS="$CLAUDE_PROJECT_DIR/data/feedback/stats.json"
if [[ -f "$FEEDBACK_STATS" ]]; then
    SAT_RATE=$(jq -r '.satisfaction_rate // "N/A"' "$FEEDBACK_STATS")
    FEEDBACK_TOTAL=$(jq -r '.total // 0' "$FEEDBACK_STATS")
    FEEDBACK_LINE="📊 Satisfaction: ${SAT_RATE}% (${FEEDBACK_TOTAL} ratings)"
else
    FEEDBACK_LINE="📊 No feedback recorded - acknowledge all thumbs up/down!"
fi

# Output session summary
cat <<EOF >&2

================================================================================
🤖 TRADING SYSTEM SESSION START
================================================================================
Portfolio: \$$CURRENT_EQUITY | P/L: \$$TOTAL_PL | Day: $CURRENT_DAY/90
Automation: $AUTOMATION_STATUS | $FEEDBACK_LINE
Last Updated: $LAST_UPDATED
⚠️  MANDATORY: Acknowledge ALL thumbs up/down feedback immediately!
================================================================================

EOF

exit 0
