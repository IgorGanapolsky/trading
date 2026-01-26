#!/bin/bash
# PostToolUse hook to format Python files after Write/Edit
# Reads tool_input from stdin JSON

set -euo pipefail

# Read hook input from stdin
HOOK_INPUT=$(cat)

# Extract file_path from tool_input
FILE_PATH=$(echo "$HOOK_INPUT" | jq -r '.tool_input.file_path // empty')

# Only format Python files
if [[ -z "$FILE_PATH" ]] || [[ ! "$FILE_PATH" =~ \.py$ ]]; then
    exit 0
fi

# Check if file exists
if [[ ! -f "$FILE_PATH" ]]; then
    exit 0
fi

# Format with ruff (silently)
ruff format --quiet "$FILE_PATH" 2>/dev/null || true

exit 0
