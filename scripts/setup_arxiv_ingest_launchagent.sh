#!/usr/bin/env bash
# Install / remove / status the local continuous arXiv ingestion LaunchAgent.
# AGENT-364 — research-only; never submits trades.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="com.igor.trading-arxiv-ingest"
TEMPLATE="${REPO_ROOT}/ops/launchd/${LABEL}.plist"
DEST="${HOME}/Library/LaunchAgents/${LABEL}.plist"
LOG_DIR="${REPO_ROOT}/logs"

usage() {
	cat <<EOF
Usage: $0 {install|remove|status|run-once}

  install   Write LaunchAgent plist and load it (every 6h + RunAtLoad)
  remove    Unload and delete the LaunchAgent
  status    Show launchctl state + last status JSON if present
  run-once  Execute one ingestion job in the foreground
EOF
}

_uid() {
	id -u
}

render_plist() {
	local python_bin="${REPO_ROOT}/.venv/bin/python"
	if [[ ! -x ${python_bin} ]]; then
		python_bin="$(command -v python3)"
	fi
	mkdir -p "$(dirname "${DEST}")" "${LOG_DIR}"
	# Substitute repo root and ensure python path is absolute
	sed -e "s|__REPO_ROOT__|${REPO_ROOT}|g" "${TEMPLATE}" |
		sed -e "s|${REPO_ROOT}/.venv/bin/python|${python_bin}|g" >"${DEST}"
}

cmd_install() {
	render_plist
	local uid
	uid="$(_uid)"
	launchctl bootout "gui/${uid}/${LABEL}" 2>/dev/null || true
	launchctl bootstrap "gui/${uid}" "${DEST}"
	launchctl enable "gui/${uid}/${LABEL}" 2>/dev/null || true
	echo "Installed and loaded: ${DEST}"
	echo "Logs: ${LOG_DIR}/arxiv_ingest.out.log"
	echo "Status: ${REPO_ROOT}/data/runtime/arxiv_ingestion_latest.json"
}

cmd_remove() {
	local uid
	uid="$(_uid)"
	launchctl bootout "gui/${uid}/${LABEL}" 2>/dev/null || true
	rm -f "${DEST}"
	echo "Removed ${LABEL}"
}

cmd_status() {
	local uid
	uid="$(_uid)"
	launchctl print "gui/${uid}/${LABEL}" 2>/dev/null || echo "LaunchAgent not loaded"
	if [[ -f ${REPO_ROOT}/data/runtime/arxiv_ingestion_latest.json ]]; then
		echo "--- last status ---"
		cat "${REPO_ROOT}/data/runtime/arxiv_ingestion_latest.json"
	else
		echo "No status file yet"
	fi
}

cmd_run_once() {
	local python_bin="${REPO_ROOT}/.venv/bin/python"
	if [[ ! -x ${python_bin} ]]; then
		python_bin="$(command -v python3)"
	fi
	cd "${REPO_ROOT}"
	PYTHONPATH="${REPO_ROOT}" "${python_bin}" scripts/arxiv_paper_ingestion.py \
		--max-results 15 --rebuild-index --json
}

main() {
	local action="${1-}"
	case ${action} in
	install) cmd_install ;;
	remove) cmd_remove ;;
	status) cmd_status ;;
	run-once) cmd_run_once ;;
	*)
		usage
		exit 1
		;;
	esac
}

main "$@"
