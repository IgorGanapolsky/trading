#!/bin/bash
# Auto-switch GitHub account to IgorGanapolsky for this project
# Runs on SessionStart to ensure correct identity

REQUIRED_ACCOUNT="IgorGanapolsky"

# Check current active account
current=$(gh auth status 2>&1 | grep "Active account: true" -B2 | grep "account" | head -1 | awk '{print $NF}' | tr -d '()')

if [ "$current" != "$REQUIRED_ACCOUNT" ]; then
    # Switch to correct account
    gh auth switch --user "$REQUIRED_ACCOUNT" >/dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "Switched GitHub account to $REQUIRED_ACCOUNT"
    fi
fi

# Export for subprocesses
export GH_USER="$REQUIRED_ACCOUNT"
