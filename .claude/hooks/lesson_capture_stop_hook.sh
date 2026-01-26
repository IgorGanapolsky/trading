#!/bin/bash
# .claude/hooks/lesson_capture_stop_hook.sh
# Stop hook that prompts Claude to capture lessons before ending session
#
# Per Claude Code docs: Stop hooks can use "decision": "block" to prevent stopping
# This ensures lessons are captured to RAG before session ends

set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-/home/user/trading}"
LESSONS_DIR="$PROJECT_DIR/rag_knowledge/lessons_learned"
STATE_FILE="$PROJECT_DIR/.claude/lesson_capture_state.json"

# Read JSON input from stdin
INPUT=$(cat)

# Extract stop_hook_active to prevent infinite loops
STOP_HOOK_ACTIVE=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('stop_hook_active', False))" 2>/dev/null || echo "False")

# If we already prompted for lessons, don't block again
if [ "$STOP_HOOK_ACTIVE" = "True" ]; then
    exit 0
fi

# Check if lesson was created this session by looking at recent files
TODAY=$(date +%Y-%m-%d)
RECENT_LESSON=$(find "$LESSONS_DIR" -name "*.md" -newermt "$TODAY" -type f 2>/dev/null | head -1 || true)

# Check if state file indicates lesson was captured
LESSON_CAPTURED="false"
if [ -f "$STATE_FILE" ]; then
    LESSON_CAPTURED=$(python3 -c "
import json
try:
    with open('$STATE_FILE') as f:
        state = json.load(f)
    print('true' if state.get('lesson_captured_this_session', False) else 'false')
except:
    print('false')
" 2>/dev/null || echo "false")
fi

# If a lesson was created today or state says captured, allow stop
if [ -n "$RECENT_LESSON" ] || [ "$LESSON_CAPTURED" = "true" ]; then
    # Clean state for next session
    rm -f "$STATE_FILE" 2>/dev/null || true
    exit 0
fi

# Check transcript for significant work indicators
TRANSCRIPT_PATH=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('transcript_path', ''))" 2>/dev/null || echo "")

SIGNIFICANT_WORK="false"
if [ -n "$TRANSCRIPT_PATH" ] && [ -f "$TRANSCRIPT_PATH" ]; then
    # Check if transcript contains indicators of significant work
    if grep -qiE "(bug|fix|error|refactor|implement|create|update|migration|lesson|learn)" "$TRANSCRIPT_PATH" 2>/dev/null; then
        SIGNIFICANT_WORK="true"
    fi
fi

# If significant work was done but no lesson captured, prompt for capture
if [ "$SIGNIFICANT_WORK" = "true" ]; then
    # Output JSON to block stopping and prompt Claude
    cat << 'EOF'
{
  "decision": "block",
  "reason": "LESSON CAPTURE REQUIRED: Significant work was done this session but no lesson was recorded to RAG. Before stopping, please:\n\n1. Reflect on what was learned this session\n2. If there's a valuable insight, create a lesson file in rag_knowledge/lessons_learned/\n3. Use format: ll_NNN_description_monthday.md\n4. If no lesson needed, say 'No lesson required' and I'll allow stopping\n\nTo skip lesson capture, run: echo '{\"lesson_captured_this_session\": true}' > .claude/lesson_capture_state.json"
}
EOF
    exit 0
fi

# No significant work detected, allow normal stop
exit 0
