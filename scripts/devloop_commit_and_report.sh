#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

LOG_FILE="${LOG_FILE:-$REPO_ROOT/artifacts/devloop/auto_commit.log}"
BRANCH="${BRANCH:-$(git rev-parse --abbrev-ref HEAD)}"
ENFORCE_PR_GREEN="${ENFORCE_PR_GREEN:-1}"
PR_NUMBER="${PR_NUMBER:-}"
SYNC_GDOC="${SYNC_GDOC:-0}"
GDRIVE_DOC_URL="${GDRIVE_DOC_URL:-}"
GDRIVE_CREDS_FILE="${GDRIVE_CREDS_FILE:-.secrets/google-service-account.json}"
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

resolve_pr_number() {
  if [[ -n "$PR_NUMBER" ]]; then
    echo "$PR_NUMBER"
    return 0
  fi
  if ! command -v gh >/dev/null 2>&1; then
    echo ""
    return 0
  fi
  gh pr list --head "$BRANCH" --state open --json number -q '.[0].number' 2>/dev/null || true
}

wait_for_green_checks() {
  if [[ "$ENFORCE_PR_GREEN" != "1" ]]; then
    return 0
  fi
  if ! command -v gh >/dev/null 2>&1; then
    log "gh not available; skipping PR-green enforcement"
    return 0
  fi
  local pr
  pr="$(resolve_pr_number)"
  if [[ -z "$pr" ]]; then
    log "no PR found for branch $BRANCH; skipping PR-green enforcement"
    return 0
  fi
  log "waiting for PR checks to complete (PR #$pr)"
  if gh pr checks "$pr" --watch --interval 15 >>"$LOG_FILE" 2>&1; then
    log "PR #$pr checks are green"
    return 0
  fi
  log "PR #$pr checks are not green; review required"
  return 2
}

generate_report() {
  log "generate morning report start"
  "$PYTHON_BIN" scripts/generate_morning_report.py --repo-root . --out artifacts/devloop/morning_report.md >>"$LOG_FILE" 2>&1
  "$PYTHON_BIN" scripts/generate_system_explainer.py --repo-root . --out docs/_reports/hackathon-system-explainer.md >>"$LOG_FILE" 2>&1 || true
  if [[ "$SYNC_GDOC" == "1" ]] && [[ -n "$GDRIVE_DOC_URL" ]]; then
    "$PYTHON_BIN" scripts/sync_explainer_to_gdoc.py --doc "$GDRIVE_DOC_URL" --in docs/_reports/hackathon-system-explainer.md --creds "$GDRIVE_CREDS_FILE" >>"$LOG_FILE" 2>&1 || true
  fi
  log "generate morning report done"
}

stage_targets() {
  # Stage only product-facing outputs, not devloop internals.
  git add -f \
    artifacts/tars/env_status.txt \
    artifacts/tars/judge_demo_checklist.md \
    artifacts/tars/resilience_report.txt \
    artifacts/tars/retrieval_report.txt \
    artifacts/tars/execution_quality_events.jsonl \
    artifacts/tars/execution_quality_daily.json \
    artifacts/tars/execution_quality_daily.md \
    artifacts/tars/smoke_metrics.txt \
    artifacts/tars/smoke_response.json \
    artifacts/tars/trade_opinion_smoke.json \
    artifacts/tars/submission_summary.md \
    || true
  git add \
    src \
    tests \
    scripts \
    data \
    docs \
    docs/_reports/hackathon-system-explainer.md \
    data/rag/lessons_query.json \
    docs/data/rag/lessons_query.json \
    docs/lessons/index.html \
    || true

  # Never publish internal loop orchestration / prompting mechanics.
  git restore --staged \
    scripts/continuous_devloop.sh \
    scripts/devloop_launchagent.sh \
    scripts/devloop_resource_guard.sh \
    scripts/devloop_resource_guard_launchagent.sh \
    scripts/monitor_devloops.sh \
    scripts/devloop_self_heal.sh \
    scripts/loop_monitor_launchagent.sh \
    scripts/layered_tdd_loop.sh \
    scripts/generate_layered_tasks.py \
    scripts/generate_next_copilot_prompt.py \
    scripts/enforce_layer1_focus.py \
    manual_layer1_tasks.md \
    config/manual_layer1_tasks.md \
    artifacts/devloop \
    || true
}

commit_changes() {
  log "auto-commit start (branch=$BRANCH)"
  git config user.name "jnrahme"
  git config user.email "jnrahme@users.noreply.github.com"
  stage_targets
  if git diff --cached --quiet; then
    log "no staged changes; skipping commit"
    return 0
  fi
  local ts
  ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  git commit -m "chore(product): auto snapshot ${ts}" >>"$LOG_FILE" 2>&1
  git push origin "$BRANCH" >>"$LOG_FILE" 2>&1
  wait_for_green_checks
  log "auto-commit done"
}

usage() {
  cat <<EOF
Usage: $0 <commit|report|both>

Commands:
  commit  Generate report, stage known artifacts, commit/push if changed.
  report  Generate morning report only.
  both    Report then commit (default).

Environment:
  ENFORCE_PR_GREEN=1  Wait for PR checks and fail if not green after push.
  PR_NUMBER=3452      Optional explicit PR number.
  SYNC_GDOC=1         Sync explainer to Google Doc during report step.
  GDRIVE_DOC_URL=...  Google Doc URL or ID.
  GDRIVE_CREDS_FILE=... Service account JSON path.
EOF
}

main() {
  local cmd="${1:-both}"
  case "$cmd" in
    commit)
      generate_report
      commit_changes
      ;;
    report)
      generate_report
      ;;
    both)
      generate_report
      commit_changes
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"
