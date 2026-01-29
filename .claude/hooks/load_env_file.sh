#!/bin/bash
# SessionStart hook: Load .env into CLAUDE_ENV_FILE so all hooks and bash commands
# have access to environment variables (Alpaca keys, API keys, etc.)
#
# Per Claude Code docs: CLAUDE_ENV_FILE is a file path where you can persist
# environment variables for subsequent bash commands in the session.

set -euo pipefail

ENV_FILE="$CLAUDE_PROJECT_DIR/.env"

if [ ! -f "$ENV_FILE" ]; then
    exit 0
fi

if [ -z "${CLAUDE_ENV_FILE:-}" ]; then
    exit 0
fi

# Parse .env and write export statements to CLAUDE_ENV_FILE
# Skip comments, blank lines, and don't override existing env vars
while IFS= read -r line || [ -n "$line" ]; do
    # Skip empty lines and comments
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue

    # Extract key=value
    if [[ "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
        key="${BASH_REMATCH[1]}"
        value="${BASH_REMATCH[2]}"
        # Strip surrounding quotes
        value="${value#\"}"
        value="${value%\"}"
        value="${value#\'}"
        value="${value%\'}"
        # Only set if not already in environment
        if [ -z "${!key:-}" ]; then
            echo "export ${key}='${value}'" >> "$CLAUDE_ENV_FILE"
        fi
    fi
done < "$ENV_FILE"

exit 0
