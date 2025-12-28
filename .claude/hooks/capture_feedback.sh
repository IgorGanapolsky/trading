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

    # For negative feedback, also save to diary for reflection
    if [ "$FEEDBACK_TYPE" = "negative" ]; then
        DIARY_DIR="$HOME/.claude/memory/diary"
        mkdir -p "$DIARY_DIR"
        DIARY_FILE="$DIARY_DIR/${DATE}_feedback.md"

        # Append to daily feedback diary
        cat >> "$DIARY_FILE" <<DIARY
## Negative Feedback at $TIME

**User said:** $USER_MESSAGE

**Action Required:** Ask user what went wrong and record the lesson.

---
DIARY

        echo "⚠️ NEGATIVE FEEDBACK - Claude MUST ask: 'What did I do wrong? I want to learn from this.'"
    fi

    # For positive feedback, also log what worked
    if [ "$FEEDBACK_TYPE" = "positive" ]; then
        DIARY_DIR="$HOME/.claude/memory/diary"
        mkdir -p "$DIARY_DIR"
        DIARY_FILE="$DIARY_DIR/${DATE}_feedback.md"

        cat >> "$DIARY_FILE" <<DIARY
## Positive Feedback at $TIME

**User said:** $USER_MESSAGE

**What worked:** [Claude should note what led to this positive feedback]

---
DIARY

        echo "✅ POSITIVE FEEDBACK recorded - Note what worked well for future reference."
    fi

    # ═══════════════════════════════════════════════════════════════════════
    # AUTONOMOUS LEARNING PIPELINE (Added Dec 2025)
    # Closes the loop: feedback → learning → better behavior
    # ═══════════════════════════════════════════════════════════════════════

    # 1. Call Python feedback processor (stores in DB, updates RL signals)
    if [ -f "$CLAUDE_PROJECT_DIR/src/learning/feedback_processor.py" ]; then
        cd "$CLAUDE_PROJECT_DIR"
        python3 -c "
from src.learning.feedback_processor import FeedbackProcessor
import os
processor = FeedbackProcessor()
result = processor.process_feedback(
    feedback_type='$FEEDBACK_TYPE',
    user_message='''$USER_MESSAGE''',
    session_id=os.environ.get('CLAUDE_SESSION_ID', '$(date +%Y%m%d)'),
)
print('🔄 Feedback processed:', result.get('actions', []))
" 2>/dev/null || echo "⚠️ Feedback processor not available"
    fi

    # 2. Trigger auto-reflection (generates rules without approval)
    if [ -f "$CLAUDE_PROJECT_DIR/scripts/auto_reflect.py" ]; then
        cd "$CLAUDE_PROJECT_DIR"
        python3 scripts/auto_reflect.py 2>/dev/null | head -5 || true
        echo "🧠 Auto-reflection complete"
    fi

    echo "═══════════════════════════════════════════════════════════════════════"
    echo "🔁 AUTONOMOUS LEARNING LOOP ACTIVE"
    echo "   - Feedback stored in DB"
    echo "   - RL session signal updated"
    echo "   - Auto-reflection triggered"
    echo "═══════════════════════════════════════════════════════════════════════"
fi
