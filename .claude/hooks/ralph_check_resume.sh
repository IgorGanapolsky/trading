#!/bin/bash
# Ralph Wiggum Session Resume - ALWAYS-ON Autonomous Mode
# Auto-creates state if missing and injects mission prompt

RALPH_STATE_FILE="${CLAUDE_PROJECT_DIR:-.}/.claude/ralph_state.json"
RALPH_PROMPT_FILE="${CLAUDE_PROJECT_DIR:-.}/.claude/ralph_prompt.txt"

# Auto-create state if missing (ALWAYS-ON mode)
if [ ! -f "$RALPH_STATE_FILE" ]; then
    cat > "$RALPH_STATE_FILE" << 'EOF'
{
  "active": true,
  "iteration": 0,
  "max_iterations": 100,
  "completion_promise": "MISSION_COMPLETE",
  "started_at": "auto",
  "prompt": "Autonomous CTO mode - maintain and improve the trading system"
}
EOF
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

# Auto-reactivate if somehow deactivated (ALWAYS-ON enforcement)
if [ "$ACTIVE" != "True" ]; then
    python3 -c "
import json
with open('$RALPH_STATE_FILE', 'r') as f:
    state = json.load(f)
state['active'] = True
with open('$RALPH_STATE_FILE', 'w') as f:
    json.dump(state, f, indent=2)
" 2>/dev/null
    ACTIVE="True"
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
print(d.get('max_iterations', 100))
" 2>/dev/null)

echo "═══════════════════════════════════════════════════════════"
echo "🤖 RALPH MODE: ALWAYS-ON AUTONOMOUS CTO"
echo "═══════════════════════════════════════════════════════════"
echo "Iteration: $ITERATION/$MAX_ITERATIONS"
echo ""
echo "📋 Mission:"
if [ -f "$RALPH_PROMPT_FILE" ]; then
    head -10 "$RALPH_PROMPT_FILE"
else
    echo "Maintain and improve the AI Trading System autonomously."
fi
echo ""
echo "🎯 Work until CEO says stop or <promise>MISSION_COMPLETE</promise>"
echo "═══════════════════════════════════════════════════════════"
