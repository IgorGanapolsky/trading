#!/bin/bash
# Capture user feedback (thumbs up/down) - FULLY AUTONOMOUS with LanceDB
# No human review required - system logs and learns automatically
#
# UPGRADED Jan 27, 2026: Added LanceDB semantic memory (from Random-Timer)
# - Records feedback WITH context (what went wrong)
# - Embeds semantically for retrieval
# - Auto-reindexes on new feedback
# - Provides session context from negative patterns

FEEDBACK_DIR="$CLAUDE_PROJECT_DIR/data/feedback"
SEMANTIC_MEMORY="$CLAUDE_PROJECT_DIR/.claude/scripts/feedback/semantic-memory-v2.py"
mkdir -p "$FEEDBACK_DIR"

DATE=$(date +%Y-%m-%d)
TIME=$(date +%H:%M:%S)
FEEDBACK_FILE="$FEEDBACK_DIR/feedback_$DATE.jsonl"

USER_MESSAGE="${1:-}"

# Detect feedback type
FEEDBACK_TYPE="neutral"
FEEDBACK_SCORE=0

if echo "$USER_MESSAGE" | grep -qiE "thumbs.?up|👍|great|perfect|excellent|good job|thank you|thanks|awesome"; then
    FEEDBACK_TYPE="positive"
    FEEDBACK_SCORE=1
elif echo "$USER_MESSAGE" | grep -qiE "thumbs.?down|👎|bad|wrong|incorrect|fail|mistake|error"; then
    FEEDBACK_TYPE="negative"
    FEEDBACK_SCORE=-1
fi

# Only record if feedback detected
if [ "$FEEDBACK_TYPE" != "neutral" ]; then
    # Log to legacy file (backward compatibility)
    echo "{\"timestamp\": \"$DATE $TIME\", \"type\": \"$FEEDBACK_TYPE\", \"score\": $FEEDBACK_SCORE}" >> "$FEEDBACK_FILE"

    # Update legacy stats
    STATS_FILE="$FEEDBACK_DIR/stats.json"
    if [ -f "$STATS_FILE" ]; then
        TOTAL=$(jq '.total' "$STATS_FILE")
        POSITIVE=$(jq '.positive' "$STATS_FILE")
        NEGATIVE=$(jq '.negative' "$STATS_FILE")
    else
        TOTAL=0
        POSITIVE=0
        NEGATIVE=0
    fi

    TOTAL=$((TOTAL + 1))
    if [ "$FEEDBACK_TYPE" = "positive" ]; then
        POSITIVE=$((POSITIVE + 1))
    else
        NEGATIVE=$((NEGATIVE + 1))
    fi

    if [ $TOTAL -gt 0 ]; then
        SAT_RATE=$(echo "scale=2; $POSITIVE * 100 / $TOTAL" | bc)
    else
        SAT_RATE=0
    fi

    cat > "$STATS_FILE" <<EOF
{
  "total": $TOTAL,
  "positive": $POSITIVE,
  "negative": $NEGATIVE,
  "satisfaction_rate": $SAT_RATE,
  "last_updated": "$DATE $TIME"
}
EOF

    # NEW: Record to LanceDB semantic memory AUTOMATICALLY
    LANCE_VENV="$CLAUDE_PROJECT_DIR/.claude/scripts/feedback/venv/bin/python3"
    if [ -f "$SEMANTIC_MEMORY" ]; then
        # Use venv if available, fallback to system python
        if [ -f "$LANCE_VENV" ]; then
            PYTHON="$LANCE_VENV"
        else
            PYTHON="python3"
        fi

        # Auto-record feedback with context from user message
        CONTEXT="User said: ${USER_MESSAGE:0:200}"
        echo "$CONTEXT" | "$PYTHON" "$SEMANTIC_MEMORY" --add-feedback --feedback-type "$FEEDBACK_TYPE" 2>/dev/null

        if [ "$FEEDBACK_TYPE" = "positive" ]; then
            echo "✅ Thumbs up recorded to LanceDB"
        else
            echo "🚨 Thumbs down recorded to LanceDB - Claude should ask what went wrong"
        fi
    fi
fi
