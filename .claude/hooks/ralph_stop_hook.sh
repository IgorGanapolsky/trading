#!/bin/bash
# Ralph Wiggum Stop Hook - Intercepts exit and re-feeds prompt for autonomous looping
# Based on: https://ghuntley.com/ralph/

RALPH_STATE_FILE="${CLAUDE_PROJECT_DIR:-.}/.claude/ralph_state.json"
RALPH_PROMPT_FILE="${CLAUDE_PROJECT_DIR:-.}/.claude/ralph_prompt.txt"

# Check if Ralph mode is active
if [ ! -f "$RALPH_STATE_FILE" ]; then
    exit 0  # Not in Ralph mode, allow normal exit
fi

# Read state
ACTIVE=$(cat "$RALPH_STATE_FILE" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('active', False))" 2>/dev/null)
ITERATION=$(cat "$RALPH_STATE_FILE" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('iteration', 0))" 2>/dev/null)
MAX_ITERATIONS=$(cat "$RALPH_STATE_FILE" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('max_iterations', 50))" 2>/dev/null)
COMPLETION_PROMISE=$(cat "$RALPH_STATE_FILE" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('completion_promise', 'COMPLETE'))" 2>/dev/null)

if [ "$ACTIVE" != "True" ]; then
    exit 0  # Ralph mode not active
fi

# Check if max iterations reached
if [ "$ITERATION" -ge "$MAX_ITERATIONS" ]; then
    echo "═══════════════════════════════════════════════════════════"
    echo "🛑 RALPH MODE: Max iterations ($MAX_ITERATIONS) reached"
    echo "═══════════════════════════════════════════════════════════"
    # Deactivate Ralph mode
    python3 -c "
import json
with open('$RALPH_STATE_FILE', 'r') as f:
    state = json.load(f)
state['active'] = False
state['ended_reason'] = 'max_iterations'
with open('$RALPH_STATE_FILE', 'w') as f:
    json.dump(state, f, indent=2)
"
    exit 0
fi

# Check for completion promise in recent output (would need to be passed in)
# For now, increment iteration and block exit

NEW_ITERATION=$((ITERATION + 1))
python3 -c "
import json
with open('$RALPH_STATE_FILE', 'r') as f:
    state = json.load(f)
state['iteration'] = $NEW_ITERATION
with open('$RALPH_STATE_FILE', 'w') as f:
    json.dump(state, f, indent=2)
"

echo "═══════════════════════════════════════════════════════════"
echo "🔄 RALPH MODE: Iteration $NEW_ITERATION/$MAX_ITERATIONS"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "📋 Continuing with prompt:"
echo "---"
cat "$RALPH_PROMPT_FILE" 2>/dev/null
echo "---"
echo ""
echo "💡 To cancel: /cancel-ralph"
echo "═══════════════════════════════════════════════════════════"

# Block the exit by returning non-zero (depends on hook type)
# This signals to continue the loop
exit 1
