#!/usr/bin/env bash
# shellcheck disable=SC2312
# Session Start Hook - ASYNC (Background tasks)
#
# Runs in background from session-start.sh. Non-blocking.
# Tasks: LanceDB context, cortex sync, health check, stale memory cleanup
#
# LOCAL ONLY - Do not commit to repository

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.claude/scripts/feedback/venv"
HEALTH_FILE="${PROJECT_ROOT}/.claude/memory/health-status.json"

# Load .env
if [[ -f "${PROJECT_ROOT}/.env" ]]; then
	# shellcheck disable=SC2046
	export $(grep -v '^#' "${PROJECT_ROOT}/.env" | grep -E '^[A-Z_]+=.' | xargs)
fi

# --- Task 1: LanceDB Semantic Memory ---
SEMANTIC_MEMORY="${PROJECT_ROOT}/.claude/scripts/feedback/semantic-memory-v2.py"
LANCE_DIR="${PROJECT_ROOT}/.claude/memory/feedback/lancedb"

if [[ -d ${VENV_DIR} ]] && [[ -f ${SEMANTIC_MEMORY} ]]; then
	# Check if LanceDB has data
	LANCE_FILES=$(find "${LANCE_DIR}" -name "*.lance" 2>/dev/null | wc -l | xargs)
	if [[ ${LANCE_FILES} -eq 0 ]]; then
		# LanceDB empty — trigger reindex from feedback log
		FEEDBACK_LOG="${PROJECT_ROOT}/.claude/memory/feedback/feedback-log.jsonl"
		if [[ -f ${FEEDBACK_LOG} ]] && [[ -s ${FEEDBACK_LOG} ]]; then
			"${VENV_DIR}/bin/python3" "${SEMANTIC_MEMORY}" --index 2>/dev/null || true
		fi
	fi
	# Load context regardless
	"${VENV_DIR}/bin/python3" "${SEMANTIC_MEMORY}" --context >/tmp/claude-semantic-context.txt 2>&1 || true
fi

# --- Task 2: Cortex RLHF Sync ---
CORTEX_SYNC="${PROJECT_ROOT}/.claude/scripts/feedback/cortex_sync.py"
PENDING_FILE="${PROJECT_ROOT}/.claude/memory/feedback/pending_cortex_sync.jsonl"

if [[ -f ${CORTEX_SYNC} ]] && [[ -f ${PENDING_FILE} ]] && [[ -s ${PENDING_FILE} ]]; then
	if [[ -x "${VENV_DIR}/bin/python3" ]]; then
		"${VENV_DIR}/bin/python3" "${CORTEX_SYNC}" --session-start 2>/dev/null || true
	elif command -v python3 &>/dev/null; then
		python3 "${CORTEX_SYNC}" --session-start 2>/dev/null || true
	fi
fi

# --- Task 3: Health Check ---
HEALTH_CHECK="${PROJECT_ROOT}/.claude/scripts/feedback/health-check.py"
if [[ -d ${VENV_DIR} ]] && [[ -f ${HEALTH_CHECK} ]]; then
	"${VENV_DIR}/bin/python3" "${HEALTH_CHECK}" --startup 2>/dev/null || true
fi

# --- Task 4: LanceDB Health Status ---
LANCE_FILES_COUNT=$(find "${LANCE_DIR}" -name "*.lance" 2>/dev/null | wc -l | xargs)
FEEDBACK_ENTRIES=$(wc -l <"${PROJECT_ROOT}/.claude/memory/feedback/feedback-log.jsonl" 2>/dev/null | xargs || echo "0")
MODEL_UPDATED=$(python3 -c "import json; print(json.load(open('${PROJECT_ROOT}/.claude/memory/feedback/feedback_model.json'))['updated'])" 2>/dev/null || echo "unknown")

cat >"${HEALTH_FILE}" <<EOF
{
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "lancedb": {
    "status": "$([[ ${LANCE_FILES_COUNT} -gt 0 ]] && echo "healthy" || echo "degraded")",
    "lance_files": ${LANCE_FILES_COUNT},
    "directory": ".claude/memory/feedback/lancedb/"
  },
  "feedback": {
    "total_entries": ${FEEDBACK_ENTRIES},
    "log_file": ".claude/memory/feedback/feedback-log.jsonl"
  },
  "thompson_model": {
    "last_updated": "${MODEL_UPDATED}",
    "model_file": ".claude/memory/feedback/feedback_model.json"
  }
}
EOF

# --- Task 5: Ralph Mode Status ---
RALPH_SCRIPT="${PROJECT_ROOT}/.claude/scripts/ralph-loop.sh"
RALPH_STATE="${PROJECT_ROOT}/.claude/ralph/state.json"

if [[ -f ${RALPH_SCRIPT} ]] && [[ -f ${RALPH_STATE} ]]; then
	RALPH_STATUS=$(jq -r '.status // "none"' "${RALPH_STATE}" 2>/dev/null || echo "none")
	if [[ ${RALPH_STATUS} == "executing" ]] || [[ ${RALPH_STATUS} == "paused" ]]; then
		RALPH_DESC=$(jq -r '.description // "unknown"' "${RALPH_STATE}" 2>/dev/null || echo "unknown")
		echo "[ASYNC] Incomplete Ralph work: ${RALPH_DESC} (${RALPH_STATUS})" >>/tmp/claude-async-status.txt
	fi
fi
