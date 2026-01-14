#!/bin/bash
# Ralph Wiggum Prompt Injector - Re-injects prompt during active Ralph loop
# Runs on UserPromptSubmit to remind Claude of the ongoing task

RALPH_STATE_FILE="${CLAUDE_PROJECT_DIR:-.}/.claude/ralph_state.json"
RALPH_PROMPT_FILE="${CLAUDE_PROJECT_DIR:-.}/.claude/ralph_prompt.txt"

# Check if Ralph mode is active
if [ ! -f "$RALPH_STATE_FILE" ]; then
    exit 0  # Not in Ralph mode
fi

# Read state
ACTIVE=$(python3 -c "
import json
try:
    with open('$RALPH_STATE_FILE') as f:
        d = json.load(f)
    print(d.get('active', False))
except:
    print(False)
" 2>/dev/null)

if [ "$ACTIVE" != "True" ]; then
    exit 0  # Ralph mode not active
fi

ITERATION=$(python3 -c "
import json
with open('$RALPH_STATE_FILE') as f:
    d = json.load(f)
print(d.get('iteration', 0))
" 2>/dev/null)

MAX_ITERATIONS=$(python3 -c "
import json
with open('$RALPH_STATE_FILE') as f:
    d = json.load(f)
print(d.get('max_iterations', 50))
" 2>/dev/null)

COMPLETION_PROMISE=$(python3 -c "
import json
with open('$RALPH_STATE_FILE') as f:
    d = json.load(f)
print(d.get('completion_promise', 'COMPLETE'))
" 2>/dev/null)

echo "═══════════════════════════════════════════════════════════"
echo "🔄 RALPH MODE ACTIVE: Iteration $ITERATION/$MAX_ITERATIONS"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "📋 Current Task:"
cat "$RALPH_PROMPT_FILE" 2>/dev/null
echo ""
echo "✅ Completion signal: Output <promise>$COMPLETION_PROMISE</promise> when done"
echo "🛑 To cancel: /cancel-ralph"
echo "═══════════════════════════════════════════════════════════"
