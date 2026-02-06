#!/usr/bin/env bash
# Pre-Work Validation — Run before any task
# Adapted from shared-core pattern (Feb 2026)
#
# Checks: venv, API keys, gh auth, RLHF state, LanceDB health, model freshness
# Exit 0 = all good, Exit 1 = blocking issue

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.claude/scripts/feedback/venv"
PASS=0
WARN=0
FAIL=0

check_pass() {
	echo "  [PASS] $1"
	((PASS++))
}
check_warn() {
	echo "  [WARN] $1"
	((WARN++))
}
check_fail() {
	echo "  [FAIL] $1"
	((FAIL++))
}

echo "Pre-Work Validation"
echo "==================="

# 1. Python venv
if [[ -x "${VENV_DIR}/bin/python3" ]]; then
	check_pass "Python venv available"
else
	check_warn "Python venv missing (${VENV_DIR}) — some RLHF features degraded"
fi

# 2. API keys
if [[ -f "${PROJECT_ROOT}/.env" ]]; then
	# shellcheck disable=SC2046
	export $(grep -v '^#' "${PROJECT_ROOT}/.env" | grep -E '^[A-Z_]+=.' | xargs) 2>/dev/null || true
	if [[ -n ${ALPACA_PAPER_TRADING_API_KEY-} ]]; then
		check_pass "Alpaca API key set"
	else
		check_warn "ALPACA_PAPER_TRADING_API_KEY not set"
	fi
else
	check_fail ".env file missing"
fi

# 3. GitHub CLI
if command -v gh &>/dev/null; then
	if gh auth status &>/dev/null 2>&1; then
		check_pass "GitHub CLI authenticated"
	else
		check_warn "GitHub CLI not authenticated (gh auth login)"
	fi
else
	check_warn "GitHub CLI not installed"
fi

# 4. Recent RLHF violations
FEEDBACK_LOG="${PROJECT_ROOT}/.claude/memory/feedback/feedback-log.jsonl"
if [[ -f ${FEEDBACK_LOG} ]]; then
	NEG_COUNT=$(tail -5 "${FEEDBACK_LOG}" | grep -c '"signal":\s*"negative' 2>/dev/null || echo "0")
	if [[ ${NEG_COUNT} -gt 3 ]]; then
		check_warn "Last 5 feedback entries: ${NEG_COUNT} negative — review before continuing"
	else
		check_pass "Recent feedback: ${NEG_COUNT}/5 negative"
	fi
else
	check_warn "No feedback log found"
fi

# 5. LanceDB health
LANCE_DIR="${PROJECT_ROOT}/.claude/memory/feedback/lancedb"
if [[ -d ${LANCE_DIR} ]]; then
	LANCE_FILES=$(find "${LANCE_DIR}" -name "*.lance" 2>/dev/null | wc -l | xargs)
	if [[ ${LANCE_FILES} -gt 0 ]]; then
		check_pass "LanceDB: ${LANCE_FILES} .lance files"
	else
		check_warn "LanceDB empty — run semantic-memory-v2.py --index"
	fi
else
	check_warn "LanceDB directory missing"
fi

# 6. Thompson model freshness
MODEL_FILE="${PROJECT_ROOT}/.claude/memory/feedback/feedback_model.json"
if [[ -f ${MODEL_FILE} ]]; then
	MODEL_DATE=$(python3 -c "import json; print(json.load(open('${MODEL_FILE}'))['updated'])" 2>/dev/null || echo "")
	if [[ -n ${MODEL_DATE} ]]; then
		# Check if model updated in last 24h
		MODEL_EPOCH=$(date -j -f "%Y-%m-%dT%H:%M:%S" "${MODEL_DATE%%.*}" +%s 2>/dev/null || echo "0")
		NOW_EPOCH=$(date +%s)
		AGE_HOURS=$(((NOW_EPOCH - MODEL_EPOCH) / 3600))
		if [[ ${AGE_HOURS} -lt 24 ]]; then
			check_pass "Thompson model: updated ${AGE_HOURS}h ago"
		else
			check_warn "Thompson model stale: updated ${AGE_HOURS}h ago — run train_from_feedback.py --train"
		fi
	else
		check_warn "Thompson model: cannot read update timestamp"
	fi
else
	check_warn "Thompson model file missing"
fi

# Summary
echo ""
echo "Result: ${PASS} passed, ${WARN} warnings, ${FAIL} failures"

if [[ ${FAIL} -gt 0 ]]; then
	echo "BLOCKED: Fix failures before proceeding"
	exit 1
fi

if [[ ${WARN} -gt 2 ]]; then
	echo "CAUTION: Multiple warnings — review before complex tasks"
fi

exit 0
