#!/bin/bash
# Ralph Wiggum Prompt Injector - Re-injects prompt during active Ralph loop
# Runs on UserPromptSubmit to remind Claude of the ongoing task
# Enhanced with PRD.json task tracking and progress.txt memory

RALPH_STATE_FILE="${CLAUDE_PROJECT_DIR:-.}/.claude/ralph_state.json"
RALPH_PROMPT_FILE="${CLAUDE_PROJECT_DIR:-.}/.claude/ralph_prompt.txt"
RALPH_PRD_FILE="${CLAUDE_PROJECT_DIR:-.}/.claude/prd.json"
RALPH_PROGRESS_FILE="${CLAUDE_PROJECT_DIR:-.}/.claude/progress.txt"

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

# Show PRD task backlog status if exists
if [ -f "$RALPH_PRD_FILE" ]; then
    PENDING=$(python3 -c "
import json
try:
    with open('$RALPH_PRD_FILE') as f:
        d = json.load(f)
    tasks = d.get('tasks', [])
    pending = [t for t in tasks if not t.get('passes', False)]
    for t in sorted(pending, key=lambda x: x.get('priority', 99))[:3]:
        print(f\"  [{t['id']}] {t['title']}\")
except Exception as e:
    pass
" 2>/dev/null)
    if [ -n "$PENDING" ]; then
        echo "📝 Next tasks from PRD:"
        echo "$PENDING"
        echo ""
    fi
fi

# Show recent progress if exists
if [ -f "$RALPH_PROGRESS_FILE" ]; then
    LAST_NOTES=$(tail -10 "$RALPH_PROGRESS_FILE" 2>/dev/null | grep "NEXT ITERATION" -A5 | head -5)
    if [ -n "$LAST_NOTES" ]; then
        echo "💡 Previous iteration notes:"
        echo "$LAST_NOTES"
        echo ""
    fi
fi

echo "Core Directives:"
echo "- Don't lose money (Phil Town Rule #1)"
echo "- Never argue with CEO"
echo "- Never tell CEO to do manual work - DO IT YOURSELF"
echo "- Always show evidence with claims"
echo "- Never lie - verify before claiming done"
echo "- Use PRs for all changes"
echo ""
echo "🎯 Work until CEO says stop or <promise>$COMPLETION_PROMISE</promise>"
echo "═══════════════════════════════════════════════════════════"
