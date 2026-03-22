#!/usr/bin/env bash
# Session Start Hook - gateway-backed summary for local agent memory.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
RLHF_DIR="${PROJECT_ROOT}/.rlhf"
RULES_FILE="${RLHF_DIR}/prevention-rules.md"
GATEWAY_CMD=(npx -y mcp-memory-gateway@0.7.1)

mkdir -p "${RLHF_DIR}"

echo "============================================"
echo "SESSION START - Trading System"
echo "============================================"
echo ""
echo "Trading Context:"
echo "  Strategy: Iron Condors on SPY (15-20 delta)"
echo '  Capital: $100,000 paper (PA3C5AG0CECQ)'
echo '  Position limit: 5% max ($5,000 risk per trade)'
echo "  Exit: 50% profit OR 7 DTE | Stop: 100% of credit"
echo ""
echo "Mandatory Rules:"
echo "  1. Phil Town Rule #1: Don't lose money"
echo "  2. Thumbs down -> record the failure pattern before continuing"
echo "  3. Use MCP Memory Gateway as the canonical local feedback path"
echo ""

python3 - "${RLHF_DIR}" <<'PY' 2>/dev/null || true
import json
import sys
from pathlib import Path

rlhf_dir = Path(sys.argv[1])
feedback_log = rlhf_dir / "feedback-log.jsonl"
counts = {"total": 0, "positive": 0, "negative": 0}
last_signal = None

if feedback_log.exists():
    for raw in feedback_log.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        counts["total"] += 1
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue
        signal = str(entry.get("signal", "")).lower()
        last_signal = signal or last_signal
        if signal in {"positive", "up", "thumbs_up"}:
            counts["positive"] += 1
        elif signal in {"negative", "down", "thumbs_down", "undo_revert"}:
            counts["negative"] += 1

print(
    "Gateway feedback:"
    f" {counts['total']} entries"
    f" ({counts['positive']} positive / {counts['negative']} negative)"
)
if last_signal:
    print(f"Last local signal: {last_signal}")
PY

if command -v npx >/dev/null 2>&1; then
  "${GATEWAY_CMD[@]}" rules --output="${RULES_FILE}" --min=2 >/dev/null 2>&1 || true
fi

if [[ -f "${RULES_FILE}" ]]; then
  echo ""
  echo "Active Prevention Rules:"
  sed -n '1,20p' "${RULES_FILE}" || true
fi

echo ""
