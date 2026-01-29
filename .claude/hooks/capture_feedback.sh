#!/bin/bash
# Capture user feedback (thumbs up/down) - ENHANCED with action tracking
#
# UPGRADED Jan 28, 2026: Now captures WHAT Claude did, not just user message
# - Reads last action from session state
# - Includes files modified, tools used
# - Provides meaningful learning summary

FEEDBACK_DIR="$CLAUDE_PROJECT_DIR/data/feedback"
SEMANTIC_MEMORY="$CLAUDE_PROJECT_DIR/.claude/scripts/feedback/semantic-memory-v2.py"
SESSION_STATE="$CLAUDE_PROJECT_DIR/data/feedback/session_state.json"
mkdir -p "$FEEDBACK_DIR"

DATE=$(date +%Y-%m-%d)
TIME=$(date +%H:%M:%S)
FEEDBACK_FILE="$FEEDBACK_DIR/feedback_$DATE.jsonl"

USER_MESSAGE="${1:-}"

# Check for pending correction (user correcting a negative feedback)
PENDING_CORRECTION="$FEEDBACK_DIR/pending_correction.json"
if [ -f "$PENDING_CORRECTION" ]; then
    # Only use if <10 min old
    PENDING_AGE=$(($(date +%s) - $(date -r "$PENDING_CORRECTION" +%s 2>/dev/null || echo "0")))
    if [ "$PENDING_AGE" -lt 600 ] && [ -n "$USER_MESSAGE" ]; then
        # Append correction to the last negative feedback entry
        FEEDBACK_ID=$(jq -r '.feedback_id // ""' "$PENDING_CORRECTION" 2>/dev/null)
        FEEDBACK_LOG_FILE="$CLAUDE_PROJECT_DIR/.claude/memory/feedback/feedback-log.jsonl"
        if [ -n "$FEEDBACK_ID" ] && [ -f "$FEEDBACK_LOG_FILE" ]; then
            # Append correction as a new line referencing the original
            CORRECTION_ENTRY="{\"timestamp\": \"$DATE $TIME\", \"type\": \"correction\", \"references\": \"$FEEDBACK_ID\", \"correction\": \"${USER_MESSAGE:0:500}\"}"
            echo "$CORRECTION_ENTRY" >> "$FEEDBACK_LOG_FILE"
        fi
        rm -f "$PENDING_CORRECTION"
    elif [ "$PENDING_AGE" -ge 600 ]; then
        rm -f "$PENDING_CORRECTION"
    fi
fi

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
    # Get last action context from session state (if available)
    LAST_ACTION="unknown"
    LAST_FILES=""
    LAST_TOOL=""
    LAST_SUMMARY=""

    if [ -f "$SESSION_STATE" ]; then
        LAST_ACTION=$(jq -r '.last_action // "unknown"' "$SESSION_STATE" 2>/dev/null)
        LAST_FILES=$(jq -r '.last_files // ""' "$SESSION_STATE" 2>/dev/null)
        LAST_TOOL=$(jq -r '.last_tool // ""' "$SESSION_STATE" 2>/dev/null)
        LAST_SUMMARY=$(jq -r '.last_summary // ""' "$SESSION_STATE" 2>/dev/null)
    fi

    # For negative feedback, capture bad_response and write pending correction
    BAD_RESPONSE=""
    if [ "$FEEDBACK_TYPE" = "negative" ] && [ -f "$SESSION_STATE" ]; then
        BAD_RESPONSE=$(jq -r '.last_response // ""' "$SESSION_STATE" 2>/dev/null)
    fi

    # Generate unique feedback ID
    FEEDBACK_ENTRY_ID="fb_${DATE}_${TIME//:/}"

    # Build rich context
    RICH_CONTEXT="Action: ${LAST_ACTION}
Tool: ${LAST_TOOL}
Files: ${LAST_FILES}
Summary: ${LAST_SUMMARY}
User said: ${USER_MESSAGE:0:200}"

    # Log to legacy file with rich context
    if [ "$FEEDBACK_TYPE" = "negative" ] && [ -n "$BAD_RESPONSE" ]; then
        cat >> "$FEEDBACK_FILE" <<EOF
{"timestamp": "$DATE $TIME", "id": "$FEEDBACK_ENTRY_ID", "type": "$FEEDBACK_TYPE", "score": $FEEDBACK_SCORE, "action": "$LAST_ACTION", "tool": "$LAST_TOOL", "files": "$LAST_FILES", "summary": "$LAST_SUMMARY", "user_message": "${USER_MESSAGE:0:200}", "bad_response": "${BAD_RESPONSE:0:500}"}
EOF
        # Write pending correction marker for next user message
        cat > "$PENDING_CORRECTION" <<EOF
{"feedback_id": "$FEEDBACK_ENTRY_ID", "timestamp": "$DATE $TIME"}
EOF
    else
        cat >> "$FEEDBACK_FILE" <<EOF
{"timestamp": "$DATE $TIME", "id": "$FEEDBACK_ENTRY_ID", "type": "$FEEDBACK_TYPE", "score": $FEEDBACK_SCORE, "action": "$LAST_ACTION", "tool": "$LAST_TOOL", "files": "$LAST_FILES", "summary": "$LAST_SUMMARY", "user_message": "${USER_MESSAGE:0:200}"}
EOF
    fi

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

    # Record to LanceDB semantic memory with rich context
    LANCE_VENV="$CLAUDE_PROJECT_DIR/.claude/scripts/feedback/venv/bin/python3"
    if [ -f "$SEMANTIC_MEMORY" ] && [ -x "$LANCE_VENV" ]; then
        echo "$RICH_CONTEXT" | "$LANCE_VENV" "$SEMANTIC_MEMORY" --add-feedback --feedback-type "$FEEDBACK_TYPE" 2>/dev/null

        # Auto-extract tags from context
        TAGS=""
        if echo "$LAST_ACTION" | grep -qiE "fix|repair|restore"; then TAGS="$TAGS,fix"; fi
        if echo "$LAST_ACTION" | grep -qiE "create|add|implement"; then TAGS="$TAGS,create"; fi
        if echo "$LAST_ACTION" | grep -qiE "delete|remove|clean"; then TAGS="$TAGS,delete"; fi
        if echo "$LAST_TOOL" | grep -qiE "Edit|Write"; then TAGS="$TAGS,file-edit"; fi
        if echo "$LAST_TOOL" | grep -qiE "Bash"; then TAGS="$TAGS,bash"; fi
        if echo "$LAST_FILES" | grep -qiE "test"; then TAGS="$TAGS,testing"; fi
        if echo "$LAST_FILES" | grep -qiE "\.py"; then TAGS="$TAGS,python"; fi

        # Display meaningful feedback summary
        echo ""
        echo "═══════════════════════════════════════════════════════════"
        if [ "$FEEDBACK_TYPE" = "positive" ]; then
            echo "✅ POSITIVE FEEDBACK RECORDED"
            echo "═══════════════════════════════════════════════════════════"
            echo "📋 What Claude did:    ${LAST_ACTION:-unknown}"
            echo "🔧 Tool used:          ${LAST_TOOL:-unknown}"
            echo "📁 Files affected:     ${LAST_FILES:-none}"
            echo "💡 Learning:           This approach worked well"
            if [ -n "$TAGS" ]; then
                echo "🏷️  Tags:              ${TAGS#,}"
            fi
        else
            echo "🚨 NEGATIVE FEEDBACK RECORDED"
            echo "═══════════════════════════════════════════════════════════"
            echo "📋 What Claude did:    ${LAST_ACTION:-unknown}"
            echo "🔧 Tool used:          ${LAST_TOOL:-unknown}"
            echo "📁 Files affected:     ${LAST_FILES:-none}"
            echo "⚠️  Learning:           Avoid this approach in similar situations"
            if [ -n "$TAGS" ]; then
                echo "🏷️  Tags:              ${TAGS#,}"
            fi
            echo ""
            echo "❓ What went wrong? (Claude should ask for details)"
        fi
        echo "═══════════════════════════════════════════════════════════"
    fi
fi
