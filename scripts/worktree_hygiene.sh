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
	echo "Usage: $0 --list | --prune | --prune-merged | --check-remove PATH | --remove PATH" >&2
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
--prune-merged)
	echo "🧹 Scanning linked worktrees for safe merged removal..."
	git -C "${PROJECT_ROOT}" fetch origin
	WORKTREE_LIST="$(git -C "${PROJECT_ROOT}" worktree list)"
	while IFS= read -r line; do
		[[ -z ${line} ]] && continue
		WT_PATH=$(echo "${line}" | awk '{print $1}')
		# Skip primary root
		if [[ ${WT_PATH} == "${PROJECT_ROOT}" ]]; then
			continue
		fi
		if PYTHONPATH="${PROJECT_ROOT}" "${PYTHON_BIN}" \
			"${PROJECT_ROOT}/scripts/agent_coordination.py" \
			--repo-root "${PROJECT_ROOT}" protect-worktree --path "${WT_PATH}" >/dev/null 2>&1; then
			echo "✅ Removing merged worktree: ${WT_PATH}"
			git -C "${PROJECT_ROOT}" worktree remove "${WT_PATH}" || rm -rf "${WT_PATH}"
		else
			echo "🔒 Keeping protected/active worktree: ${WT_PATH}"
		fi
	done <<<"${WORKTREE_LIST}"
	git -C "${PROJECT_ROOT}" worktree prune --verbose || true
	echo "✨ Merged worktree pruning complete."
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
