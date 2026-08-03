#!/usr/bin/env bash
# Session Start Hook - compact trading context plus shared ThumbGate summary.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"

echo "============================================"
echo "SESSION START - Trading System"
echo "============================================"
echo ""
echo "Trading Context:"
echo "  Strategy: SPY put-credit validation (paper only)"
echo "  Entry: scripts/spy_put_credit.py"
echo "  Residual IC: exit-only via scripts/residual_ic_manager.py"
echo "  New IC entries: killed by data/runtime/strategy_kill_switch.json"
echo "  Promotion: blocked until n>=30, expectancy>0, and profit factor>1"
echo ""
echo "Mandatory Rules:"
echo "  1. Phil Town Rule #1: Don't lose money"
echo "  2. Thumbs down -> record the failure pattern before continuing"
echo "  3. Use ThumbGate as the canonical local feedback path"
echo ""

python3 "${PROJECT_ROOT}/scripts/thumbgate_session_start.py" || true
echo ""
