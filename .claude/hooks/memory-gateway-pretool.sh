#!/usr/bin/env bash
# Run ThumbGate gate checks inside the repo's existing GSD PreToolUse hook.

set -euo pipefail

TOOL_COMMAND="${1-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CUSTOM_GATES="${PROJECT_ROOT}/config/memory-gateway/gates.json"
THUMBGATE_CMD=(npx --yes --package thumbgate@0.9.13 thumbgate gate-check)

HOOK_JSON="$(
	python3 - "${TOOL_COMMAND}" <<'PY'
import json
import sys

command = sys.argv[1] if len(sys.argv) > 1 else ""
print(json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}))
PY
)"

RESULT="$(printf '%s' "${HOOK_JSON}" | RLHF_GATES_CONFIG="${CUSTOM_GATES}" "${THUMBGATE_CMD[@]}" 2>/dev/null || true)"

if [[ -z ${RESULT} || ${RESULT} == "{}" ]]; then
	exit 0
fi

printf '%s\n' "${RESULT}"

if printf '%s' "${RESULT}" | grep -q '"permissionDecision"[[:space:]]*:[[:space:]]*"deny"'; then
	exit 2
fi

exit 0
