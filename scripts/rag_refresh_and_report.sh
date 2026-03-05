#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

FORCE="${FORCE:-0}"
if [[ -z "${RAG_WRITE_PROFILE:-}" ]]; then
  if [[ "${CI:-}" == "true" ]]; then
    RAG_WRITE_PROFILE="repo"
  else
    RAG_WRITE_PROFILE="local"
  fi
fi
export RAG_WRITE_PROFILE

if [[ "${RAG_WRITE_PROFILE}" == "repo" ]]; then
  DEFAULT_DEVLOOP_DIR="$REPO_ROOT/artifacts/devloop"
else
  DEFAULT_DEVLOOP_DIR="$REPO_ROOT/artifacts/local/devloop"
fi
DEVLOOP_DIR="${DEVLOOP_DIR:-$DEFAULT_DEVLOOP_DIR}"
LOG_FILE="${LOG_FILE:-$DEVLOOP_DIR/rag_refresh.log}"
OUT_REPORT="${OUT_REPORT:-$DEVLOOP_DIR/rag_status.md}"
STATUS_FILE="${STATUS_FILE:-$DEVLOOP_DIR/rag_refresh_status.txt}"
TARS_INGEST_SCRIPT="$REPO_ROOT/scripts/ingest_tars_artifacts_to_rag.py"
TARS_VALIDATE_SCRIPT="$REPO_ROOT/scripts/generate_tars_rag_validation.py"
if [[ -x "$REPO_ROOT/.venv-devloop/bin/python" ]]; then
  PYTHON_BIN="${PYTHON_BIN:-$REPO_ROOT/.venv-devloop/bin/python}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE"
touch "$STATUS_FILE"

log() {
  local msg="$1"
  printf "[%s] %s\n" "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "$msg" | tee -a "$LOG_FILE"
}

run_reindex() {
  log "RAG reindex start (force=$FORCE)"
  local cmd_exit=0
  local health_exit=0
  local exit_code=0
  set +e
  if [[ "$FORCE" == "1" ]]; then
    "$PYTHON_BIN" scripts/reindex_rag.py --force >>"$LOG_FILE" 2>&1
  else
    "$PYTHON_BIN" scripts/reindex_rag.py >>"$LOG_FILE" 2>&1
  fi
  cmd_exit=$?
  "$PYTHON_BIN" - <<'PY' >>"$LOG_FILE" 2>&1
import json
from pathlib import Path
stats = Path(".claude/memory/lancedb/index_stats.json")
if not stats.exists():
    raise SystemExit(2)
payload = json.loads(stats.read_text(encoding="utf-8", errors="ignore"))
errors = payload.get("errors", [])
raise SystemExit(1 if isinstance(errors, list) and len(errors) > 0 else 0)
PY
  health_exit=$?
  set -e
  if [[ "$cmd_exit" -ne 0 ]] || [[ "$health_exit" -ne 0 ]]; then
    exit_code=1
  fi
  printf "reindex_exit=%s\n" "$exit_code" >>"$STATUS_FILE"
  log "RAG reindex done (exit=$exit_code cmd=$cmd_exit health=$health_exit)"
}

run_tars_ingest() {
  if [[ ! -f "$TARS_INGEST_SCRIPT" ]]; then
    printf "tars_ingest_exit=0\n" >>"$STATUS_FILE"
    printf "tars_ingest_skipped=missing_script\n" >>"$STATUS_FILE"
    log "TARS artifact ingest skipped (missing script: $TARS_INGEST_SCRIPT)"
    return 0
  fi

  log "TARS artifact ingest to RAG start"
  local exit_code=0
  set +e
  "$PYTHON_BIN" "$TARS_INGEST_SCRIPT" \
    --artifact-dir artifacts/tars \
    --out-dir rag_knowledge/lessons_learned \
    --manifest "$DEVLOOP_DIR/tars_rag_ingest_manifest.json" \
    --report "$DEVLOOP_DIR/tars_rag_ingest_report.md" >>"$LOG_FILE" 2>&1
  exit_code=$?
  set -e
  printf "tars_ingest_exit=%s\n" "$exit_code" >>"$STATUS_FILE"
  log "TARS artifact ingest to RAG done (exit=$exit_code)"
}

snapshot_index_stats() {
  local out="$1"
  local src="$REPO_ROOT/.claude/memory/lancedb/index_stats.json"
  if [[ -f "$src" ]]; then
    cp "$src" "$out"
  else
    printf '{"files_processed":0,"chunks_created":0,"errors":["missing_index_stats"]}\n' >"$out"
  fi
}

run_tars_rag_validation() {
  local before_stats="$DEVLOOP_DIR/index_stats_before_tars_ingest.json"
  local after_stats="$DEVLOOP_DIR/index_stats_after_tars_ingest.json"
  snapshot_index_stats "$before_stats"
  run_tars_ingest
  run_reindex
  snapshot_index_stats "$after_stats"

  if [[ ! -f "$TARS_VALIDATE_SCRIPT" ]]; then
    printf "tars_rag_validation_exit=0\n" >>"$STATUS_FILE"
    printf "tars_rag_validation_skipped=missing_script\n" >>"$STATUS_FILE"
    log "TARS->RAG validation skipped (missing script: $TARS_VALIDATE_SCRIPT)"
    return 0
  fi

  log "TARS->RAG validation artifact generation start"
  local exit_code=0
  set +e
  "$PYTHON_BIN" "$TARS_VALIDATE_SCRIPT" \
    --before-stats "$before_stats" \
    --after-stats "$after_stats" \
    --ingest-report "$DEVLOOP_DIR/tars_rag_ingest_report.md" \
    --out-json "$DEVLOOP_DIR/tars_rag_validation.json" \
    --out-md "$DEVLOOP_DIR/tars_rag_validation.md" >>"$LOG_FILE" 2>&1
  exit_code=$?
  set -e
  printf "tars_rag_validation_exit=%s\n" "$exit_code" >>"$STATUS_FILE"
  log "TARS->RAG validation artifact generation done (exit=$exit_code)"
}

run_query_index() {
  log "RAG query-index build start"
  local exit_code=0
  set +e
  "$PYTHON_BIN" scripts/build_rag_query_index.py >>"$LOG_FILE" 2>&1
  exit_code=$?
  set -e
  printf "query_index_exit=%s\n" "$exit_code" >>"$STATUS_FILE"
  log "RAG query-index build done (exit=$exit_code)"
}

run_status_report() {
  log "RAG status report generation start"
  local exit_code=0
  set +e
  "$PYTHON_BIN" scripts/generate_rag_status_report.py --repo-root . --out "$OUT_REPORT" --refresh-log "$LOG_FILE" --status-file "$STATUS_FILE" >>"$LOG_FILE" 2>&1
  exit_code=$?
  set -e
  printf "report_exit=%s\n" "$exit_code" >>"$STATUS_FILE"
  log "RAG status report generation done (exit=$exit_code)"
}

usage() {
  cat <<EOF
Usage: $0 <refresh|report|full>

Commands:
  refresh  Run reindex + query index update.
  tars     Run TARS artifact ingest + reindex + validation.
  report   Generate status report only.
  full     Run tars ingest/validation, refresh, and then generate status report.

Environment:
  FORCE=1           Force rebuild reindex table
  RAG_WRITE_PROFILE repo|local (default: repo on CI, local otherwise)
  DEVLOOP_DIR=...   Artifact directory (default based on RAG_WRITE_PROFILE)
  LOG_FILE=...      Refresh log path (default: \$DEVLOOP_DIR/rag_refresh.log)
  OUT_REPORT=...    Status report path (default: \$DEVLOOP_DIR/rag_status.md)
  STATUS_FILE=...   Step status path (default: \$DEVLOOP_DIR/rag_refresh_status.txt)
  PYTHON_BIN=...    Python executable (default: .venv-devloop/bin/python if present)
EOF
}

main() {
  local cmd="${1:-full}"
  mkdir -p "$DEVLOOP_DIR"
  case "$cmd" in
    report)
      touch "$STATUS_FILE"
      ;;
    *)
      : > "$STATUS_FILE"
      ;;
  esac
  case "$cmd" in
    refresh)
      run_reindex
      run_query_index
      ;;
    tars)
      run_tars_rag_validation
      run_query_index
      ;;
    report)
      run_status_report
      ;;
    full)
      run_tars_rag_validation
      run_query_index
      run_status_report
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"
