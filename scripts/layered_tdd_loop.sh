#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARTIFACT_DIR="${ARTIFACT_DIR:-$REPO_ROOT/artifacts/devloop}"
MAX_ITERS="${MAX_ITERS:-5}"
DEVLOOP_VENV="${DEVLOOP_VENV:-$REPO_ROOT/.venv-devloop}"
PROFILE="${PROFILE:-profit}"

if [[ -x "$DEVLOOP_VENV/bin/ruff" ]]; then
  _default_ruff="$DEVLOOP_VENV/bin/ruff"
else
  _default_ruff="ruff"
fi

if [[ -x "$DEVLOOP_VENV/bin/pytest" ]]; then
  _default_pytest="$DEVLOOP_VENV/bin/pytest"
else
  _default_pytest="pytest"
fi

if [[ "$PROFILE" == "full" ]]; then
  _profile_pytest_cmd="$_default_pytest tests/ -q --maxfail=25 --tb=short"
  _profile_ruff_cmd="$_default_ruff check src/ scripts/ --select=E9,F63,F7,F82"
else
  _profile_pytest_cmd="$_default_pytest tests/test_orchestrator_main.py tests/test_trade_gateway.py tests/test_risk_manager.py tests/test_pre_trade_checklist.py tests/test_options_executor_smoke.py tests/test_trade_opinion.py -q --maxfail=25 --tb=short"
  _profile_ruff_cmd="$_default_ruff check src/orchestrator src/risk src/trading src/execution src/llm scripts --select=E9,F63,F7,F82"
fi

PYTEST_CMD="${PYTEST_CMD:-$_profile_pytest_cmd}"
RUFF_CMD="${RUFF_CMD:-$_profile_ruff_cmd}"

mkdir -p "$ARTIFACT_DIR"

run_iteration() {
  local iter="$1"
  local iter_dir="$ARTIFACT_DIR/iter_${iter}"
  mkdir -p "$iter_dir"

  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] iteration=$iter" | tee "$iter_dir/meta.txt"

  set +e
  bash -lc "$RUFF_CMD" >"$iter_dir/ruff.log" 2>&1
  local ruff_exit=$?
  bash -lc "$PYTEST_CMD" >"$iter_dir/pytest.log" 2>&1
  local pytest_exit=$?
  set -e

  {
    echo "ruff_exit=$ruff_exit"
    echo "pytest_exit=$pytest_exit"
  } >>"$iter_dir/meta.txt"

  python3 "$REPO_ROOT/scripts/generate_layered_tasks.py" \
    --repo-root "$REPO_ROOT" \
    --ruff-log "$iter_dir/ruff.log" \
    --pytest-log "$iter_dir/pytest.log" \
    --out "$iter_dir/tasks.md" \
    --lint-exit "$ruff_exit" \
    --test-exit "$pytest_exit"

  cp "$iter_dir/tasks.md" "$ARTIFACT_DIR/tasks.md"
  cp "$iter_dir/meta.txt" "$ARTIFACT_DIR/status.txt"
  python3 "$REPO_ROOT/scripts/generate_profit_readiness_scorecard.py" \
    --repo-root "$REPO_ROOT" \
    --artifact-dir "$ARTIFACT_DIR" \
    --out "$ARTIFACT_DIR/profit_readiness_scorecard.md" >/dev/null 2>&1 || true
  python3 "$REPO_ROOT/scripts/generate_kpi_page.py" \
    --repo-root "$REPO_ROOT" \
    --out "$ARTIFACT_DIR/kpi_page.md" >/dev/null 2>&1 || true

  if [[ $ruff_exit -eq 0 && $pytest_exit -eq 0 ]]; then
    echo "iteration $iter: green"
    return 0
  fi

  echo "iteration $iter: not green"
  return 1
}

usage() {
  cat <<EOF
Usage: $0 <bootstrap|analyze|run>

Commands:
  bootstrap Run local tool bootstrap in .venv-devloop.
  analyze   Run a single pass and generate layered tasks.
  run       Run iterative loop up to MAX_ITERS until checks are green.

Env overrides:
  ARTIFACT_DIR  (default: artifacts/devloop)
  MAX_ITERS     (default: 5)
  PROFILE       (default: profit; options: profit, full)
  DEVLOOP_VENV  (default: .venv-devloop)
  RUFF_CMD      (default: profile-based command)
  PYTEST_CMD    (default: profile-based command)
EOF
}

bootstrap_tools() {
  python3 -m venv "$DEVLOOP_VENV"
  "$DEVLOOP_VENV/bin/pip" install -q --upgrade pip
  if [[ -f "$REPO_ROOT/requirements-minimal.txt" ]]; then
    "$DEVLOOP_VENV/bin/pip" install -q -r "$REPO_ROOT/requirements-minimal.txt"
  fi
  "$DEVLOOP_VENV/bin/pip" install -q ruff pytest
  echo "bootstrap complete: $DEVLOOP_VENV"
  echo "profile: $PROFILE"
  echo "ruff cmd: $RUFF_CMD"
  echo "pytest cmd: $PYTEST_CMD"
}

preflight_tools() {
  local missing=0
  local missing_msgs=()
  if ! command -v python3 >/dev/null 2>&1; then
    missing_msgs+=("python3")
    missing=1
  fi
  if ! bash -lc "command -v ${RUFF_CMD%% *}" >/dev/null 2>&1; then
    missing_msgs+=("${RUFF_CMD%% *}")
    missing=1
  fi
  if ! bash -lc "command -v ${PYTEST_CMD%% *}" >/dev/null 2>&1; then
    missing_msgs+=("${PYTEST_CMD%% *}")
    missing=1
  fi
  if (( missing == 1 )); then
    {
      echo "# Layered Task Backlog"
      echo
      echo "## Gate Status"
      echo "- Lint: BLOCKED"
      echo "- Tests: BLOCKED"
      echo
      echo "## Layer 1: Red Build/Test Failures"
      echo "- Install missing toolchain: ${missing_msgs[*]}"
      echo "- Or override commands with installed executables via \`RUFF_CMD\` and \`PYTEST_CMD\`."
      echo
      echo "## Layer 2: High-Impact Files"
      echo "- None (preflight blocked before analysis)."
      echo
      echo "## Layer 3: Deferred Cleanup"
      echo "- None (preflight blocked before analysis)."
      echo
      echo "## Next Loop Protocol"
      echo "1. Install tools."
      echo "2. Re-run \`./scripts/layered_tdd_loop.sh analyze\`."
      echo "3. Start fixing Layer 1 items."
    } > "$ARTIFACT_DIR/tasks.md"
  fi
  return "$missing"
}

main() {
  local cmd="${1:-}"
  case "$cmd" in
    bootstrap)
      bootstrap_tools
      ;;
    analyze)
      if ! preflight_tools; then
        echo "preflight failed; install tooling or override RUFF_CMD/PYTEST_CMD."
        exit 3
      fi
      run_iteration 1 || true
      ;;
    run)
      if ! preflight_tools; then
        echo "preflight failed; install tooling or override RUFF_CMD/PYTEST_CMD."
        exit 3
      fi
      local i
      for ((i = 1; i <= MAX_ITERS; i++)); do
        if run_iteration "$i"; then
          echo "loop complete: all checks green"
          exit 0
        fi
      done
      echo "loop stopped: reached MAX_ITERS=$MAX_ITERS while checks still failing"
      exit 2
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"
