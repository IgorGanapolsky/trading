#!/usr/bin/env bash
# shellcheck disable=SC2312,SC2016,SC2126
# Session Start Hook - SYNC (Fast, <1s)
#
# Architecture (Feb 2026 - Enterprise Standard):
# SYNC (this file): Critical context + Thompson state (<1s)
# ASYNC (session-start-async.sh): LanceDB, cortex sync, health checks (background)
#
# LOCAL ONLY - Do not commit to repository

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Single-instance lock - prevent duplicate runs across sessions
LOCK_HASH=$(echo "${PROJECT_ROOT}" | md5 2>/dev/null | awk '{print $1}' || echo "default")
LOCKFILE="/tmp/claude-project-session-${LOCK_HASH}.lock"
exec 9>"${LOCKFILE}"
flock -n 9 || exit 0

# Load .env for API keys
if [[ -f "${PROJECT_ROOT}/.env" ]]; then
	# shellcheck disable=SC2046
	export $(grep -v '^#' "${PROJECT_ROOT}/.env" | grep -E '^[A-Z_]+=.' | xargs)
fi

echo "============================================"
echo "SESSION START - Trading System"
echo "============================================"
echo ""

# TIER 1: Thompson Sampling Reliability (FAST - reads JSON only)
TRAIN_SCRIPT="${PROJECT_ROOT}/.claude/scripts/feedback/train_from_feedback.py"
MODEL_JSON="${PROJECT_ROOT}/.claude/memory/feedback/feedback_model.json"
if [[ -f ${TRAIN_SCRIPT} ]] && [[ -f ${MODEL_JSON} ]]; then
	python3 "${TRAIN_SCRIPT}" --reliability --json 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    cats = data.get('categories', {})
    print(f'  Model: {data.get(\"total_entries\", 0)} entries')
    for cat, info in sorted(cats.items(), key=lambda x: -x[1]['reliability'])[:5]:
        r = info['reliability']
        bar = '#' * int(r * 10) + '-' * (10 - int(r * 10))
        print(f'  {cat:<18s} [{bar}] {r:.0%} ({info[\"samples\"]} samples)')
except Exception:
    print('  (Model not yet trained)')
" 2>/dev/null || echo "  (Thompson Sampling not available)"
fi

# TIER 2: Trading Context (static, instant)
echo ""
echo "Trading Context:"
echo "  Strategy: Iron Condors on SPY (15-20 delta)"
echo '  Capital: $100,000 paper (PA3C5AG0CECQ)'
echo '  Position limit: 5% max ($5,000 risk per trade)'
echo "  Exit: 50% profit OR 7 DTE | Stop: 200% of credit"
echo ""

# TIER 3: Mandatory Rules (instant)
echo "MANDATORY RULES:"
echo "  1. Phil Town Rule #1: Don't lose money"
echo "  2. Thumbs down -> STOP -> Record lesson -> Apologize"
echo "  3. Compound engineering: Fix -> Test -> Prevent -> Memory -> Verify"
echo "  4. Memory/lessons are LOCAL ONLY - never commit"
echo ""

# TIER 4: Cortex Sync Status (fast check, sync action deferred to async)
PENDING_FILE="${PROJECT_ROOT}/.claude/memory/feedback/pending_cortex_sync.jsonl"
if [[ -f ${PENDING_FILE} ]] && [[ -s ${PENDING_FILE} ]]; then
	PENDING_COUNT=$(grep -c '"synced":\s*false' "${PENDING_FILE}" 2>/dev/null || echo "0")
	LEGACY_COUNT=$(grep -v '"synced"' "${PENDING_FILE}" 2>/dev/null | wc -l | xargs)
	PENDING_COUNT=${PENDING_COUNT:-0}
	LEGACY_COUNT=${LEGACY_COUNT:-0}
	TOTAL=$((PENDING_COUNT + LEGACY_COUNT))
	if [[ ${TOTAL} -gt 0 ]]; then
		echo "Cortex: ${TOTAL} pending feedback entries (async sync starting)"
	fi
fi

# TIER 5: Launch async hook in background
ASYNC_HOOK="${SCRIPT_DIR}/session-start-async.sh"
if [[ -f ${ASYNC_HOOK} ]] && [[ -x ${ASYNC_HOOK} ]]; then
	"${ASYNC_HOOK}" &
	echo "[ASYNC] Background tasks launched (LanceDB, health check, cortex sync)"
fi

echo "============================================"
echo ""
