#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

INTERVAL_SECONDS="${INTERVAL_SECONDS:-900}"
NO_SLEEP="${NO_SLEEP:-0}" # 1 = run cycles back-to-back with no pause
FULL_EVERY="${FULL_EVERY:-6}"
MAX_CYCLES="${MAX_CYCLES:-0}" # 0 = infinite
RUN_TARS="${RUN_TARS:-0}" # 1 enables TARS full run each cycle
RUN_TARS_EVERY="${RUN_TARS_EVERY:-2}" # run TARS every N cycles when enabled
RUN_RAG="${RUN_RAG:-0}" # 1 enables RAG refresh during full profile cycles
SYNC_GDOC="${SYNC_GDOC:-0}" # 1 syncs explainer into Google Doc each cycle
SYNC_GDOC_EVERY="${SYNC_GDOC_EVERY:-2}" # sync Google Doc every N cycles when enabled
RENDER_DEMO_EVERY="${RENDER_DEMO_EVERY:-2}" # regenerate judge page every N cycles
LAYER1_MAX_OPEN="${LAYER1_MAX_OPEN:-3}" # keep top N open Layer 1 tasks active
MANUAL_TASK_FILE="${MANUAL_TASK_FILE:-manual_layer1_tasks.md}"
MIRROR_MANUAL_TASK_FILE="${MIRROR_MANUAL_TASK_FILE:-config/manual_layer1_tasks.md}"
GDRIVE_DOC_URL="${GDRIVE_DOC_URL:-}"
GDRIVE_CREDS_FILE="${GDRIVE_CREDS_FILE:-.secrets/google-service-account.json}"
STOP_FILE="${STOP_FILE:-$REPO_ROOT/artifacts/devloop/STOP}"
LOG_FILE="${LOG_FILE:-$REPO_ROOT/artifacts/devloop/continuous.log}"
TARS_AUTOPILOT_SCRIPT="${TARS_AUTOPILOT_SCRIPT:-$REPO_ROOT/scripts/tars_autopilot.sh}"
PYTHON_BIN="${PYTHON_BIN:-$REPO_ROOT/.venv-devloop/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

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

  "$PYTHON_BIN" scripts/enforce_layer1_focus.py --max-open "$LAYER1_MAX_OPEN" --manual "$MANUAL_TASK_FILE" --mirror "$MIRROR_MANUAL_TASK_FILE" >>"$LOG_FILE" 2>&1 || true

  log "cycle=$cycle profile=$profile analyze start"
  if [[ "$profile" == "full" ]]; then
    PROFILE=full ./scripts/layered_tdd_loop.sh analyze >>"$LOG_FILE" 2>&1
  else
    ./scripts/layered_tdd_loop.sh analyze >>"$LOG_FILE" 2>&1
  fi
  log "cycle=$cycle profile=$profile analyze done"

  if [[ "$RUN_TARS" == "1" ]]; then
    local run_tars_cycle=1
    if (( RUN_TARS_EVERY > 1 )) && (( cycle % RUN_TARS_EVERY != 0 )); then
      run_tars_cycle=0
    fi
    if (( run_tars_cycle == 0 )); then
      log "cycle=$cycle tars skipped (cadence RUN_TARS_EVERY=$RUN_TARS_EVERY)"
    else
      if [[ -n "${LLM_GATEWAY_BASE_URL:-}" ]] && [[ -n "${LLM_GATEWAY_API_KEY:-}${TETRATE_API_KEY:-}" ]]; then
        log "cycle=$cycle tars full start"
        "$TARS_AUTOPILOT_SCRIPT" full >>"$LOG_FILE" 2>&1 || true
        log "cycle=$cycle tars full done"
      else
        log "cycle=$cycle tars skipped (gateway env missing)"
      fi
    fi
  fi

  if [[ "$RUN_RAG" == "1" ]] && [[ "$profile" == "full" ]]; then
    log "cycle=$cycle rag refresh start"
    ./scripts/rag_refresh_and_report.sh full >>"$LOG_FILE" 2>&1 || true
    log "cycle=$cycle rag refresh done"
  fi

  "$PYTHON_BIN" scripts/generate_profit_readiness_scorecard.py --repo-root . --artifact-dir artifacts/devloop --out artifacts/devloop/profit_readiness_scorecard.md >>"$LOG_FILE" 2>&1 || true
  "$PYTHON_BIN" scripts/generate_kpi_priority.py --scorecard artifacts/devloop/profit_readiness_scorecard.md --state artifacts/devloop/kpi_priority_state.json --out-md artifacts/devloop/kpi_priority_report.md --out-json artifacts/devloop/kpi_priority.json --stall-window 6 >>"$LOG_FILE" 2>&1 || true
  local expand_output
  expand_output="$("$PYTHON_BIN" scripts/expand_layers.py --tasks artifacts/devloop/tasks.md --scorecard artifacts/devloop/profit_readiness_scorecard.md --manual-file "$MANUAL_TASK_FILE" --mirror-manual-file "$MIRROR_MANUAL_TASK_FILE" --out artifacts/devloop/layer_expansion_report.md --priority-json artifacts/devloop/kpi_priority.json 2>&1 || true)"
  printf "%s\n" "$expand_output" >>"$LOG_FILE"
  if printf "%s\n" "$expand_output" | grep -q "promoted_count=[1-9]"; then
    log "cycle=$cycle promotions detected; refreshing analyze"
    ./scripts/layered_tdd_loop.sh analyze >>"$LOG_FILE" 2>&1 || true
  fi
  log "cycle=$cycle parallel artifact generation start"
  (
    "$PYTHON_BIN" scripts/generate_kpi_page.py --repo-root . --out artifacts/devloop/kpi_page.md >>"$LOG_FILE" 2>&1 || true
  ) &
  local pid_kpi=$!
  (
    "$PYTHON_BIN" scripts/generate_task_runtime_report.py --repo-root . --manual "$MANUAL_TASK_FILE" --state artifacts/devloop/task_runtime_state.json --log artifacts/devloop/continuous.log --out artifacts/devloop/task_runtime_report.md >>"$LOG_FILE" 2>&1 || true
  ) &
  local pid_runtime=$!

  log "cycle=$cycle archived demo/status page render skipped"
  local pid_demo=""
  local pid_ops=""

  (
    "$PYTHON_BIN" scripts/generate_next_copilot_prompt.py --repo-root . --out artifacts/devloop/next_copilot_prompt.md >>"$LOG_FILE" 2>&1 || true
  ) &
  local pid_prompt=$!

  wait "$pid_kpi" || true
  wait "$pid_runtime" || true
  if [[ -n "$pid_demo" ]]; then
    wait "$pid_demo" || true
  fi
  if [[ -n "$pid_ops" ]]; then
    wait "$pid_ops" || true
  fi
  wait "$pid_prompt" || true

  "$PYTHON_BIN" scripts/generate_system_explainer.py --repo-root . --out docs/_reports/hackathon-system-explainer.md >>"$LOG_FILE" 2>&1 || true

  if [[ "$SYNC_GDOC" == "1" ]] && [[ -n "$GDRIVE_DOC_URL" ]]; then
    local sync_doc_cycle=1
    if (( SYNC_GDOC_EVERY > 1 )) && (( cycle % SYNC_GDOC_EVERY != 0 )); then
      sync_doc_cycle=0
    fi
    if (( sync_doc_cycle == 1 )); then
      "$PYTHON_BIN" scripts/sync_explainer_to_gdoc.py --doc "$GDRIVE_DOC_URL" --in docs/_reports/hackathon-system-explainer.md --creds "$GDRIVE_CREDS_FILE" >>"$LOG_FILE" 2>&1 || true
    else
      log "cycle=$cycle gdoc sync skipped (cadence SYNC_GDOC_EVERY=$SYNC_GDOC_EVERY)"
    fi
  fi
  log "cycle=$cycle parallel artifact generation done"
}

usage() {
  cat <<EOF
Usage: $0 <start|once>

Commands:
  once   Run one cycle only.
  start  Run continuously until STOP file exists or MAX_CYCLES reached.

Environment:
  INTERVAL_SECONDS  Sleep between cycles (default: 900)
  NO_SLEEP          1 to run cycles continuously with no sleep (default: 0)
  FULL_EVERY        Every N cycles run PROFILE=full (default: 6)
  MAX_CYCLES        Max cycles then exit, 0=infinite (default: 0)
  RUN_TARS          1 to run TARS full each cycle (default: 0)
  RUN_TARS_EVERY    Run TARS every N cycles when RUN_TARS=1 (default: 2)
  RUN_RAG           1 to refresh RAG on full-profile cycles (default: 0)
  LAYER1_MAX_OPEN   Keep top N open Layer 1 tasks active (default: 3)
  MANUAL_TASK_FILE  Task file used by loop focus/expansion (default: manual_layer1_tasks.md)
  MIRROR_MANUAL_TASK_FILE Mirror task file (default: config/manual_layer1_tasks.md)
  RENDER_DEMO_EVERY Regenerate judge demo page every N cycles (default: 2)
  SYNC_GDOC         1 to sync explainer to Google Doc (default: 0)
  SYNC_GDOC_EVERY   Sync Google Doc every N cycles (default: 2)
  GDRIVE_DOC_URL    Google Doc URL or ID for explainer sync
  GDRIVE_CREDS_FILE Service account JSON path (default: .secrets/google-service-account.json)
  TARS_AUTOPILOT_SCRIPT Path to tars autopilot script (default: scripts/tars_autopilot.sh)
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
      # If paused by STOP_FILE, wait here instead of exiting and thrashing launchd restarts.
      while [[ -f "$STOP_FILE" ]]; do
        log "pause detected before bootstrap: $STOP_FILE"
        sleep 30
      done
      bootstrap_once
      local cycle=1
      while true; do
        if [[ -f "$STOP_FILE" ]]; then
          log "pause detected: $STOP_FILE"
          sleep 30
          continue
        fi
        run_cycle "$cycle"
        if (( MAX_CYCLES > 0 && cycle >= MAX_CYCLES )); then
          log "max cycles reached: $MAX_CYCLES"
          break
        fi
        cycle=$((cycle + 1))
        if [[ "$NO_SLEEP" == "1" ]]; then
          log "no-sleep mode enabled; starting next cycle immediately"
        else
          log "sleeping ${INTERVAL_SECONDS}s"
          sleep "$INTERVAL_SECONDS"
        fi
      done
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"
