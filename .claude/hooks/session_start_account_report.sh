#!/bin/bash
#
# Claude Code SessionStart Hook - Account Verification Report
#
# This hook runs at session start to verify all data sources match Alpaca (source of truth).
#
# CEO Directive (Jan 15, 2026):
# "Every time I start a session you are to see the latest status in Alpaca 5000 paper trading account
# and brokerage account, and report exactly how much money we made today or lost today (with brief reasons).
# In addition, you have to report what is showing on their progress dashboard and GitHub.
# Is it matching what Alpaca shows. Alpaca is the single source of truth.
# In addition to that, you need to query dialogflow and ask it the same question and verify that it matches alpaca"
#
# Created: Jan 15, 2026

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Load credentials from .env.local if available
if [[ -f "$CLAUDE_PROJECT_DIR/.env.local" ]]; then
    source "$CLAUDE_PROJECT_DIR/.env.local"
fi

# Run the session start report script
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}" >&1
echo -e "${GREEN}📊 SESSION START ACCOUNT VERIFICATION${NC}" >&1
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}" >&1

# Check if we have credentials
if [[ -z "${ALPACA_PAPER_TRADING_5K_API_KEY:-}" ]]; then
    echo -e "${YELLOW}⚠️  Alpaca credentials not found in environment${NC}" >&1
    echo -e "${YELLOW}   Credentials available in GitHub Actions only${NC}" >&1
    echo -e "${YELLOW}   Skipping live account verification${NC}" >&1
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}" >&1
    exit 0
fi

# Run the Python report script
python3 "$CLAUDE_PROJECT_DIR/scripts/session_start_report.py" >&1 2>&1

echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}" >&1
