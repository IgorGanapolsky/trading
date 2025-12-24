#!/bin/bash
# Capture user feedback (thumbs up/down) for reinforcement learning
# Called when user gives explicit feedback signals

FEEDBACK_DIR="$CLAUDE_PROJECT_DIR/data/feedback"
mkdir -p "$FEEDBACK_DIR"

DATE=$(date +%Y-%m-%d)
TIME=$(date +%H:%M:%S)
FEEDBACK_FILE="$FEEDBACK_DIR/feedback_$DATE.jsonl"

# Get the user's message (passed as argument or from stdin)
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
    # Create feedback entry
    ENTRY=$(cat <<EOF
{"timestamp": "$DATE $TIME", "type": "$FEEDBACK_TYPE", "score": $FEEDBACK_SCORE, "context": "$USER_MESSAGE"}
EOF
)
    echo "$ENTRY" >> "$FEEDBACK_FILE"

    # Update cumulative stats
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

    # Calculate satisfaction rate
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

    echo "📊 Feedback recorded: $FEEDBACK_TYPE (Total: $TOTAL, Satisfaction: ${SAT_RATE}%)"
fi
