#!/usr/bin/env bash
# Run MCP Memory Gateway gate checks inside the repo's existing GSD PreToolUse hook.

set -euo pipefail

TOOL_COMMAND="${1:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CUSTOM_GATES="${PROJECT_ROOT}/config/memory-gateway/gates.json"

resolve_global_gates_engine() {
  local global_root
  global_root="$(npm root -g 2>/dev/null || true)"
  if [[ -n "${global_root}" && -f "${global_root}/mcp-memory-gateway/scripts/gates-engine.js" ]]; then
    printf '%s\n' "${global_root}/mcp-memory-gateway/scripts/gates-engine.js"
    return 0
  fi
  return 1
}

resolve_gates_engine() {
  if [[ -n "${MCP_MEMORY_GATEWAY_GATES_ENGINE:-}" && -f "${MCP_MEMORY_GATEWAY_GATES_ENGINE}" ]]; then
    printf '%s\n' "${MCP_MEMORY_GATEWAY_GATES_ENGINE}"
    return 0
  fi

  if [[ -f "${PROJECT_ROOT}/node_modules/mcp-memory-gateway/scripts/gates-engine.js" ]]; then
    printf '%s\n' "${PROJECT_ROOT}/node_modules/mcp-memory-gateway/scripts/gates-engine.js"
    return 0
  fi

  resolve_global_gates_engine && return 0
  return 1
}

GATES_ENGINE="$(resolve_gates_engine || true)"
if [[ -z "${GATES_ENGINE}" ]]; then
  exit 0
fi

HOOK_JSON="$(python3 - "${TOOL_COMMAND}" <<'PY'
import json
import sys

command = sys.argv[1] if len(sys.argv) > 1 else ""
print(json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}))
PY
)"

RESULT="$(printf '%s' "${HOOK_JSON}" | RLHF_GATES_CONFIG="${CUSTOM_GATES}" node "${GATES_ENGINE}" 2>/dev/null || true)"

if [[ -z "${RESULT}" || "${RESULT}" == "{}" ]]; then
  exit 0
fi

printf '%s\n' "${RESULT}"

if printf '%s' "${RESULT}" | grep -q '"permissionDecision"[[:space:]]*:[[:space:]]*"deny"'; then
  exit 2
fi

exit 0
