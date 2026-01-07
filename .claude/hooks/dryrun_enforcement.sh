#!/bin/bash
#
# Dry-Run Enforcement Hook
#
# Tracks merges to main and requires a successful dry-run
# before the next trading session.
#
# This prevents deploying untested code to production trading.
#
# Runs on: PostToolUse (after Bash commands that include "git merge" or "git pull")
#

set -euo pipefail

DRYRUN_STATE="${CLAUDE_PROJECT_DIR:-/home/user/trading}/data/dryrun_state.json"

# Read hook input
HOOK_INPUT=$(cat)

# Extract the command that was run
TOOL_NAME=$(echo "$HOOK_INPUT" | jq -r '.tool_name // empty')
TOOL_INPUT=$(echo "$HOOK_INPUT" | jq -r '.tool_input // empty')

# Only process Bash commands
if [[ "$TOOL_NAME" != "Bash" ]]; then
    exit 0
fi

COMMAND=$(echo "$TOOL_INPUT" | jq -r '.command // empty')

# Check if this was a merge to main
if [[ "$COMMAND" == *"git merge"* ]] || [[ "$COMMAND" == *"git pull"* ]]; then
    # Check if we're on main branch
    CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")

    if [[ "$CURRENT_BRANCH" == "main" ]]; then
        # Record that a merge happened and dry-run is required
        mkdir -p "$(dirname "$DRYRUN_STATE")"

        python3 << PYEND
import json
from datetime import datetime
from pathlib import Path

state_file = Path("$DRYRUN_STATE")

try:
    state = json.loads(state_file.read_text()) if state_file.exists() else {}
except:
    state = {}

state["last_merge"] = datetime.now().isoformat()
state["dryrun_required"] = True
state["dryrun_completed"] = False
state["merge_command"] = """$COMMAND"""[:200]

state_file.write_text(json.dumps(state, indent=2))
PYEND

        echo ""
        echo "════════════════════════════════════════════════════════════"
        echo "🔔 MERGE TO MAIN DETECTED"
        echo "════════════════════════════════════════════════════════════"
        echo ""
        echo "A dry-run is NOW REQUIRED before the next trading session."
        echo ""
        echo "Run: python3 scripts/system_health_check.py --dry-run"
        echo ""
        echo "This ensures merged code won't break production trading."
        echo "════════════════════════════════════════════════════════════"
    fi
fi

# Check if this was a dry-run command
if [[ "$COMMAND" == *"dry-run"* ]] || [[ "$COMMAND" == *"dry_run"* ]]; then
    # Check if dry-run was successful (exit code 0)
    STDOUT=$(echo "$HOOK_INPUT" | jq -r '.stdout // empty')

    if [[ "$STDOUT" == *"PASSED"* ]] || [[ "$STDOUT" == *"SUCCESS"* ]] || [[ "$STDOUT" == *"All checks passed"* ]]; then
        python3 << PYEND
import json
from datetime import datetime
from pathlib import Path

state_file = Path("$DRYRUN_STATE")

try:
    state = json.loads(state_file.read_text()) if state_file.exists() else {}
except:
    state = {}

state["dryrun_completed"] = True
state["dryrun_completed_at"] = datetime.now().isoformat()
state["dryrun_required"] = False

state_file.write_text(json.dumps(state, indent=2))
PYEND

        echo "✅ Dry-run completed successfully. Trading is safe to proceed."
    fi
fi

exit 0
