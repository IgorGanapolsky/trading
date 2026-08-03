#!/usr/bin/env bash
# Fail closed on repository mutations without an active issue-scoped claim.

set -euo pipefail

RAW_INPUT="${1-}"
if [[ -z ${RAW_INPUT} ]]; then
	RAW_INPUT="$(cat || true)"
fi

COMMAND="$(printf '%s' "${RAW_INPUT}" | jq -r '.command // .tool_input.command // empty' 2>/dev/null || true)"
if [[ -z ${COMMAND} ]]; then
	COMMAND="${RAW_INPUT}"
fi

# Read-only Bash remains available for diagnosis. Edit/Write tools are checked
# separately by guard_destructive_actions.sh.
MUTATION_RE='(^|[;&|[:space:]])(apply_patch|rm|mv|cp|touch|mkdir|rmdir|tee)([;&|[:space:]]|$)|git[[:space:]]+(add|commit|push|merge|rebase|cherry-pick|reset|clean|checkout|switch|restore)([;&|[:space:]]|$)|sed[[:space:]]+-i|(^|[^>])>>?([^>]|$)'
WORKTREE_REMOVE_RE='git[[:space:]]+worktree[[:space:]]+(remove|prune)'

if [[ ${COMMAND} =~ ${WORKTREE_REMOVE_RE} ]]; then
	echo "BLOCKED: use scripts/worktree_hygiene.sh for claim-aware worktree cleanup" >&2
	exit 2
fi
if [[ ! ${COMMAND} =~ ${MUTATION_RE} ]]; then
	exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"
if [[ ! -x ${PYTHON_BIN} ]]; then
	PYTHON_BIN="$(command -v python3.11 || command -v python3 || true)"
fi
if [[ -z ${PYTHON_BIN} || ! -f ${PROJECT_ROOT}/scripts/agent_coordination.py ]]; then
	echo "BLOCKED: coordination preflight is unavailable" >&2
	exit 2
fi

PYTHONPATH="${PROJECT_ROOT}" "${PYTHON_BIN}" \
	"${PROJECT_ROOT}/scripts/agent_coordination.py" \
	--repo-root "${PROJECT_ROOT}" preflight >/dev/null
