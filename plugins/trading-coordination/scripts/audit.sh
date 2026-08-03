#!/usr/bin/env bash
# Run the repository audit for the Herdr invocation's worktree/cwd.

set -euo pipefail

TARGET_DIRECTORY="${HERDR_WORKTREE_PATH-${PWD}}"
if [[ -n ${HERDR_PLUGIN_CONTEXT_JSON-} ]]; then
	CONTEXT_DIRECTORY="$(python3 -c '
import json, os
data = json.loads(os.environ.get("HERDR_PLUGIN_CONTEXT_JSON", "{}"))
keys = ("worktree_path", "foreground_cwd", "cwd", "path")
def find(value):
    if isinstance(value, dict):
        for key in keys:
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate:
                return candidate
        for candidate in value.values():
            found = find(candidate)
            if found:
                return found
    if isinstance(value, list):
        for candidate in value:
            found = find(candidate)
            if found:
                return found
    return ""
print(find(data))
')"
	if [[ -n ${CONTEXT_DIRECTORY} ]]; then
		TARGET_DIRECTORY="${CONTEXT_DIRECTORY}"
	fi
fi

REPO_ROOT="$(git -C "${TARGET_DIRECTORY}" rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z ${REPO_ROOT} || ! -f ${REPO_ROOT}/scripts/agent_coordination.py ]]; then
	exit 0
fi

PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
if [[ ! -x ${PYTHON_BIN} ]]; then
	PYTHON_BIN="$(command -v python3.11 || command -v python3)"
fi
PYTHONPATH="${REPO_ROOT}" "${PYTHON_BIN}" \
	"${REPO_ROOT}/scripts/agent_coordination.py" \
	--repo-root "${REPO_ROOT}" audit --warn-only
