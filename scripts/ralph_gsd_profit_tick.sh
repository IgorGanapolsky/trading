#!/usr/bin/env bash
# Wrapper for Ralph+GSD profit tick (LaunchAgent / cron friendly).
set -euo pipefail
ROOT="$(cd "$(dirname "${0}")/.." && pwd)"
cd "${ROOT}"
if [[ -x "${ROOT}/.venv/bin/python" ]]; then
	exec "${ROOT}/.venv/bin/python" "${ROOT}/scripts/ralph_gsd_profit_tick.py"
fi
exec python3 "${ROOT}/scripts/ralph_gsd_profit_tick.py"
