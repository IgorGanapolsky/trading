#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

INTERVAL_SECONDS="${INTERVAL_SECONDS:-900}"
FULL_EVERY="${FULL_EVERY:-6}"
MAX_CYCLES="${MAX_CYCLES:-0}" # 0 = infinite
RUN_TARS="${RUN_TARS:-0}" # 1 enables TARS full run each cycle
STOP_FILE="${STOP_FILE:-$REPO_ROOT/artifacts/devloop/STOP}"
LOG_FILE="${LOG_FILE:-$REPO_ROOT/artifacts/devloop/continuous.log}"

mkdir -p "$REPO_ROOT/artifacts/devloop"
touch "$LOG_FILE"

log() {
  local msg="$1"
  printf "[%s] %s\n" "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "$msg" | tee -a "$LOG_FILE"
}

bootstrap_once() {
  log "bootstrap start"
  ./scripts/layered_tdd_loop.sh bootstrap >>"$LOG_FILE" 2>&1
  log "bootstrap done"
}

run_cycle() {
  local cycle="$1"
  local profile="profit"
  if (( FULL_EVERY > 0 )) && (( cycle % FULL_EVERY == 0 )); then
    profile="full"
  fi

  log "cycle=$cycle profile=$profile analyze start"
  if [[ "$profile" == "full" ]]; then
    PROFILE=full ./scripts/layered_tdd_loop.sh analyze >>"$LOG_FILE" 2>&1
  else
    ./scripts/layered_tdd_loop.sh analyze >>"$LOG_FILE" 2>&1
  fi
  log "cycle=$cycle profile=$profile analyze done"

  if [[ "$RUN_TARS" == "1" ]]; then
    if [[ -n "${LLM_GATEWAY_BASE_URL:-}" ]] && [[ -n "${LLM_GATEWAY_API_KEY:-}${TETRATE_API_KEY:-}" ]]; then
      log "cycle=$cycle tars full start"
      /Users/joeyrahme/.codex/skills/tars-hackathon-autopilot/scripts/tars_autopilot.sh full >>"$LOG_FILE" 2>&1 || true
      log "cycle=$cycle tars full done"
    else
      log "cycle=$cycle tars skipped (gateway env missing)"
    fi
  fi

  python3 scripts/generate_profit_readiness_scorecard.py --repo-root . --artifact-dir artifacts/devloop --out artifacts/devloop/profit_readiness_scorecard.md >>"$LOG_FILE" 2>&1 || true
  python3 scripts/generate_kpi_page.py --repo-root . --out artifacts/devloop/kpi_page.md >>"$LOG_FILE" 2>&1 || true
}

usage() {
  cat <<EOF
Usage: $0 <start|once>

Commands:
  once   Run one cycle only.
  start  Run continuously until STOP file exists or MAX_CYCLES reached.

Environment:
  INTERVAL_SECONDS  Sleep between cycles (default: 900)
  FULL_EVERY        Every N cycles run PROFILE=full (default: 6)
  MAX_CYCLES        Max cycles then exit, 0=infinite (default: 0)
  RUN_TARS          1 to run TARS full each cycle (default: 0)
  STOP_FILE         Stop marker file path
  LOG_FILE          Log file path
EOF
}

main() {
  local cmd="${1:-}"
  case "$cmd" in
    once)
      bootstrap_once
      run_cycle 1
      ;;
    start)
      bootstrap_once
      local cycle=1
      while true; do
        if [[ -f "$STOP_FILE" ]]; then
          log "stop file detected: $STOP_FILE"
          break
        fi
        run_cycle "$cycle"
        if (( MAX_CYCLES > 0 && cycle >= MAX_CYCLES )); then
          log "max cycles reached: $MAX_CYCLES"
          break
        fi
        cycle=$((cycle + 1))
        log "sleeping ${INTERVAL_SECONDS}s"
        sleep "$INTERVAL_SECONDS"
      done
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"

