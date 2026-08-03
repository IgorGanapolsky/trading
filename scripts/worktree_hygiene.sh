#!/usr/bin/env bash
# Claim-aware worktree inventory, pruning, and removal.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"
if [[ ! -x ${PYTHON_BIN} ]]; then
	PYTHON_BIN="$(command -v python3.11 || command -v python3)"
fi

usage() {
	echo "Usage: $0 --list | --prune | --check-remove PATH | --remove PATH" >&2
}

case "${1-}" in
--list)
	git -C "${PROJECT_ROOT}" worktree list
	;;
--prune)
	# Git prune removes only registrations whose directories are already gone.
	# It does not delete a worktree directory or its files.
	git -C "${PROJECT_ROOT}" worktree prune --dry-run --verbose
	git -C "${PROJECT_ROOT}" worktree prune --verbose
	;;
--check-remove | --remove)
	if [[ $# -ne 2 ]]; then
		usage
		exit 2
	fi
	TARGET_WORKTREE="$2"
	PYTHONPATH="${PROJECT_ROOT}" "${PYTHON_BIN}" \
		"${PROJECT_ROOT}/scripts/agent_coordination.py" \
		--repo-root "${PROJECT_ROOT}" protect-worktree --path "${TARGET_WORKTREE}"
	if [[ $1 == "--remove" ]]; then
		git -C "${PROJECT_ROOT}" worktree remove "${TARGET_WORKTREE}"
	fi
	;;
*)
	usage
	exit 2
	;;
esac
