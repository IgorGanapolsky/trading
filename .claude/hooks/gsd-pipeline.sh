#!/usr/bin/env bash
# Unified GSD hook pipeline.
# This script provides deterministic sequencing for Claude hook events.

set -euo pipefail

EVENT="${1:-}"
TOOL_INPUT="${2:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
export CLAUDE_PROJECT_DIR="${CLAUDE_PROJECT_DIR:-${PROJECT_ROOT}}"
LOG_DIR="${PROJECT_ROOT}/.claude/logs"
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/gsd-hook-pipeline.log"

timestamp() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

log() {
  printf '[%s] [%s] %s\n' "$(timestamp)" "${EVENT:-unknown}" "$1" >>"${LOG_FILE}"
}

run_hook() {
  local hook_name="$1"
  local hook_path="${SCRIPT_DIR}/${hook_name}"
  if [[ ! -f "${hook_path}" ]]; then
    log "missing hook: ${hook_name}"
    return 1
  fi
  bash "${hook_path}" "${@:2}"
}

if [[ -z "${EVENT}" ]]; then
  echo "Usage: $0 <session_start|user_prompt_submit|pre_tool_use> [tool_input]"
  exit 2
fi

LOCK_ID="$(printf '%s:%s' "${PROJECT_ROOT}" "${EVENT}" | shasum -a 256 | awk '{print $1}')"
LOCK_FILE="/tmp/gsd-hook-${LOCK_ID}.lock"
exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  log "skipping duplicate concurrent run"
  exit 0
fi

log "pipeline start"

case "${EVENT}" in
session_start)
  run_hook "session-start.sh"
  run_hook "inject_trading_context.sh"
  ;;
user_prompt_submit)
  USER_PROMPT="$(cat || true)"
  printf '%s' "${USER_PROMPT}" | run_hook "user-prompt-submit.sh"
  run_hook "inject_trading_context.sh"
  ;;
pre_tool_use)
  run_hook "memory-gateway-pretool.sh" "${TOOL_INPUT}"
  run_hook "block_position_close.sh" "${TOOL_INPUT}"
  run_hook "require_magic_word.sh" "${TOOL_INPUT}"
  ;;
*)
  log "unknown event: ${EVENT}"
  exit 2
  ;;
esac

log "pipeline complete"
exit 0
