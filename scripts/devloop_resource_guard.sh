#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

LOG_FILE="${LOG_FILE:-$REPO_ROOT/artifacts/devloop/resource_guard.log}"
STATE_FILE="${STATE_FILE:-$REPO_ROOT/artifacts/devloop/resource_guard_state.txt}"
CHECK_INTERVAL_SECONDS="${CHECK_INTERVAL_SECONDS:-20}"
HIGH_LOAD="${HIGH_LOAD:-12.0}"
LOW_LOAD="${LOW_LOAD:-8.0}"
MIN_FREE_GB="${MIN_FREE_GB:-0.8}"
RECOVER_FREE_GB="${RECOVER_FREE_GB:-1.5}"
STOP_FILES_CSV="${STOP_FILES_CSV:-/Users/joeyrahme/GitHubWorkspace/trading-strategy-loop/artifacts/devloop/STOP,/Users/joeyrahme/GitHubWorkspace/trading-tetrate-loop/artifacts/devloop/STOP,/Users/joeyrahme/GitHubWorkspace/trading-evidence-loop/artifacts/devloop/STOP}"

mkdir -p "$REPO_ROOT/artifacts/devloop"
touch "$LOG_FILE"

log() {
  printf "[%s] %s\n" "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "$1" | tee -a "$LOG_FILE"
}

load_1m() {
  sysctl -n vm.loadavg | awk -F'[{} ,]+' '{print $2}'
}

free_gb() {
  vm_stat | awk '
    /page size of/ { gsub(/[^0-9]/,"",$8); page_size=$8; }
    /Pages free:/ { gsub(/[^0-9]/,"",$3); free=$3; }
    /Pages speculative:/ { gsub(/[^0-9]/,"",$3); spec=$3; }
    END {
      if (page_size == 0) page_size=16384;
      bytes=(free+spec)*page_size;
      gb=bytes/1024/1024/1024;
      printf "%.2f", gb;
    }'
}

is_high() {
  local l="$1"
  local f="$2"
  awk -v l="$l" -v hl="$HIGH_LOAD" -v f="$f" -v mf="$MIN_FREE_GB" 'BEGIN { if (l >= hl || f <= mf) exit 0; exit 1; }'
}

is_recovered() {
  local l="$1"
  local f="$2"
  awk -v l="$l" -v ll="$LOW_LOAD" -v f="$f" -v rf="$RECOVER_FREE_GB" 'BEGIN { if (l <= ll && f >= rf) exit 0; exit 1; }'
}

apply_stop() {
  local file
  IFS=',' read -r -a files <<<"$STOP_FILES_CSV"
  for file in "${files[@]}"; do
    mkdir -p "$(dirname "$file")"
    : >"$file"
  done
}

clear_stop() {
  local file
  IFS=',' read -r -a files <<<"$STOP_FILES_CSV"
  for file in "${files[@]}"; do
    rm -f "$file"
  done
}

main() {
  local throttled="0"
  if [[ -f "$STATE_FILE" ]]; then
    throttled="$(cat "$STATE_FILE" 2>/dev/null || echo 0)"
  fi

  log "resource guard started (high_load=$HIGH_LOAD low_load=$LOW_LOAD min_free_gb=$MIN_FREE_GB recover_free_gb=$RECOVER_FREE_GB)"

  while true; do
    local l f
    l="$(load_1m)"
    f="$(free_gb)"

    if is_high "$l" "$f"; then
      if [[ "$throttled" != "1" ]]; then
        apply_stop
        throttled="1"
        echo "$throttled" >"$STATE_FILE"
        log "throttle=ON load_1m=$l free_gb=$f (secondary loops paused)"
      fi
    else
      if [[ "$throttled" == "1" ]] && is_recovered "$l" "$f"; then
        clear_stop
        throttled="0"
        echo "$throttled" >"$STATE_FILE"
        log "throttle=OFF load_1m=$l free_gb=$f (secondary loops resumed)"
      fi
    fi

    sleep "$CHECK_INTERVAL_SECONDS"
  done
}

main "$@"
