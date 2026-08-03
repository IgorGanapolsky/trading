#!/usr/bin/env bash
# Pre-tool guard for non-Bash tools (Edit/Write/NotebookEdit/MCP).
#
# Blocks two classes of action:
#   1. Removing or rewriting the TRADING_HALTED kill-switch file
#      (read by src/risk/trade_gateway.py; removing it re-enables trading).
#   2. Destructive Alpaca MCP calls (close_position, cancel_order, etc.).
#
# Magic-word override mirrors require_magic_word.sh: if the file
# /tmp/claude_magic_word_authorized exists, the block is consumed for ONE call.

set -euo pipefail

MAGIC_WORD_FILE="/tmp/claude_magic_word_authorized"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"

INPUT="$(cat || true)"
if [[ -z ${INPUT} ]]; then
	exit 0
fi

TOOL_NAME="$(printf '%s' "${INPUT}" | jq -r '.tool_name // empty' 2>/dev/null || echo "")"
FILE_PATH="$(printf '%s' "${INPUT}" | jq -r '.tool_input.file_path // empty' 2>/dev/null || echo "")"
NEW_STRING="$(printf '%s' "${INPUT}" | jq -r '.tool_input.new_string // empty' 2>/dev/null || echo "")"
CONTENT="$(printf '%s' "${INPUT}" | jq -r '.tool_input.content // empty' 2>/dev/null || echo "")"

KILL_SWITCH_RE='(data/TRADING_HALTED|data/SYSTEM_HALTED|data/trading_halt\.txt)'
RISK_CONST_RE='(IRON_CONDOR_STOP_LOSS_MULTIPLIER|MAX_CONCURRENT_IRON_CONDORS|NORTH_STAR_MONTHLY_AFTER_TAX|FORBIDDEN_STRATEGIES)'
DESTRUCTIVE_MCP_RE='^mcp__alpaca__(close_position|close_all_positions|cancel_order|cancel_all_orders|liquidate)'

reason=""

case "${TOOL_NAME}" in
Edit | Write | NotebookEdit | MultiEdit)
	PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"
	if [[ ! -x ${PYTHON_BIN} ]]; then
		PYTHON_BIN="$(command -v python3.11 || command -v python3 || true)"
	fi
	if [[ -z ${PYTHON_BIN} || ! -f ${PROJECT_ROOT}/scripts/agent_coordination.py ]]; then
		echo "BLOCKED: coordination preflight is unavailable" >&2
		exit 2
	fi
	if ! PYTHONPATH="${PROJECT_ROOT}" "${PYTHON_BIN}" \
		"${PROJECT_ROOT}/scripts/agent_coordination.py" \
		--repo-root "${PROJECT_ROOT}" preflight --file "${FILE_PATH}" >/dev/null; then
		echo "BLOCKED: file edit has no matching active Linear/Vault claim" >&2
		exit 2
	fi
	;;
*) ;;
esac

case "${TOOL_NAME}" in
Edit | Write | NotebookEdit | MultiEdit)
	if [[ ${FILE_PATH} =~ $KILL_SWITCH_RE ]]; then
		reason="Edit/Write targets kill-switch file (${FILE_PATH}). Removing TRADING_HALTED re-enables trade execution."
	elif [[ ${FILE_PATH} == *"trading_constants.py" ]] &&
		{ echo "${NEW_STRING}${CONTENT}" | grep -qE "$RISK_CONST_RE"; }; then
		reason="Modification of canonical risk constants in trading_constants.py. These are policy-protected."
	fi
	;;
*)
	if [[ ${TOOL_NAME} =~ $DESTRUCTIVE_MCP_RE ]]; then
		reason="Destructive Alpaca MCP call: ${TOOL_NAME}. Reconciled exits are owned by put-credit-validation.yml and its current managers."
	fi
	;;
esac

if [[ -n ${reason} ]]; then
	if [[ -f ${MAGIC_WORD_FILE} ]]; then
		rm -f "${MAGIC_WORD_FILE}"
		exit 0
	fi
	{
		echo "🚫 BLOCKED by guard_destructive_actions: ${reason}"
		echo ""
		echo "Boundary policy: .claude/rules/boundary-policy.md"
		echo "Override (one-shot): touch ${MAGIC_WORD_FILE}"
	} >&2
	exit 2
fi

exit 0
