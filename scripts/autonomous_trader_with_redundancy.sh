#!/bin/bash
# Smart wrapper for autonomous trader with GitHub Actions redundancy check
# Only runs if GitHub Actions didn't already execute successfully today

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

VENV_PYTHON="${REPO_ROOT}/.venv/bin/python3"
CHECK_SCRIPT="${SCRIPT_DIR}/check_github_actions_status.py"
TRADER_SCRIPT="${SCRIPT_DIR}/autonomous_trader.py"

# Check if GitHub Actions already ran today
echo "🔍 Checking if GitHub Actions already executed today..."
if "${VENV_PYTHON}" "${CHECK_SCRIPT}" "daily-trading.yml"; then
    echo "✅ GitHub Actions already ran successfully today - skipping local execution"
    echo "   (This is expected - GitHub Actions is primary, local is backup)"
    exit 0
fi

# GitHub Actions didn't run or failed - execute as backup
echo "⚠️  GitHub Actions didn't run successfully today - executing local backup..."
echo "   Reason: $(${VENV_PYTHON} ${CHECK_SCRIPT} daily-trading.yml 2>&1 | grep 'Reason:' || echo 'Unknown')"

# Execute the trader
exec "${VENV_PYTHON}" "${TRADER_SCRIPT}" "$@"
