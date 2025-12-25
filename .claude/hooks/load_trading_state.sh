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

# Check for recent diary entries (last 3 days)
DIARY_DIR="$HOME/.claude/memory/diary"
RECENT_LESSONS=""
if [[ -d "$DIARY_DIR" ]]; then
    # Count unprocessed diary files
    PROCESSED_LOG="$DIARY_DIR/processed.log"
    touch "$PROCESSED_LOG"
    UNPROCESSED=$(find "$DIARY_DIR" -name "*.md" -mtime -3 -type f 2>/dev/null | while read f; do
        grep -q "$f" "$PROCESSED_LOG" || echo "$f"
    done | wc -l)

    if [[ $UNPROCESSED -gt 0 ]]; then
        RECENT_LESSONS="📝 $UNPROCESSED unprocessed diary entries - run /reflect to learn from them"
    fi

    # Extract recent negative feedback for immediate attention
    RECENT_NEGATIVE=$(find "$DIARY_DIR" -name "*_feedback.md" -mtime -1 -type f 2>/dev/null | xargs grep -l "Negative Feedback" 2>/dev/null | head -1)
    if [[ -n "$RECENT_NEGATIVE" ]]; then
        RECENT_LESSONS="$RECENT_LESSONS
⚠️  Recent negative feedback detected - review and learn from it!"
    fi
fi

# Check for session-learned rules in CLAUDE.md
LEARNED_RULES=""
CLAUDE_MD="$CLAUDE_PROJECT_DIR/CLAUDE.md"
if [[ -f "$CLAUDE_MD" ]] && grep -q "Session-Learned Rules" "$CLAUDE_MD"; then
    RULE_COUNT=$(grep -A 50 "Session-Learned Rules" "$CLAUDE_MD" | grep -c "^-" 2>/dev/null || echo "0")
    if [[ $RULE_COUNT -gt 0 ]]; then
        LEARNED_RULES="📚 $RULE_COUNT session-learned rules active"
    fi
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
EOF

# Show memory/learning status if applicable
if [[ -n "$RECENT_LESSONS" ]] || [[ -n "$LEARNED_RULES" ]]; then
    cat <<EOF >&2
--------------------------------------------------------------------------------
🧠 PERSISTENT MEMORY STATUS
$RECENT_LESSONS
$LEARNED_RULES
💡 Use /diary to record session learnings, /reflect to generate rules
EOF
fi

cat <<EOF >&2
================================================================================

EOF

exit 0
