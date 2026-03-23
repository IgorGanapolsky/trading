#!/usr/bin/env bash
set -euo pipefail

MAIN_ROOT="/Users/joeyrahme/GitHubWorkspace/trading"
UID_NUM="$(id -u)"
NOW_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

OUT_MD="${OUT_MD:-$MAIN_ROOT/artifacts/devloop/self_heal_report.md}"
OUT_STATUS="${OUT_STATUS:-$MAIN_ROOT/artifacts/devloop/self_heal_status.txt}"
MAX_STALE_SECONDS="${MAX_STALE_SECONDS:-1200}"
AUTO_RESTART="${AUTO_RESTART:-1}"

mkdir -p "$(dirname "$OUT_MD")"

LOOPS=(
  "com.joeyrahme.trading.devloop|$MAIN_ROOT"
  "com.joeyrahme.trading.devloop.strategy|/Users/joeyrahme/GitHubWorkspace/trading-strategy-loop"
  "com.joeyrahme.trading.devloop.tetrate|/Users/joeyrahme/GitHubWorkspace/trading-tetrate-loop"
  "com.joeyrahme.trading.devloop.evidence|/Users/joeyrahme/GitHubWorkspace/trading-evidence-loop"
)

REQUIRED_SCRIPTS=(
  "scripts/continuous_devloop.sh"
  "scripts/enforce_layer1_focus.py"
  "scripts/generate_task_runtime_report.py"
  "scripts/generate_system_explainer.py"
)

restarts=0
sync_fixes=0
unpause_fixes=0
stale_fixes=0
actions=()

get_pid() {
  local label="$1"
  local pid
  pid="$(launchctl list | awk -v l="$label" '$3==l{print $1}')"
  if [[ -z "$pid" || "$pid" == "-" ]]; then
    echo ""
  else
    echo "$pid"
  fi
}

restart_loop() {
  local label="$1"
  launchctl kickstart -k "gui/$UID_NUM/$label" >/dev/null 2>&1 || true
  restarts=$((restarts + 1))
}

sync_required_scripts() {
  local workdir="$1"
  local fixed=0
  for rel in "${REQUIRED_SCRIPTS[@]}"; do
    src="$MAIN_ROOT/$rel"
    dst="$workdir/$rel"
    [[ -f "$src" ]] || continue
    if [[ ! -f "$dst" ]]; then
      mkdir -p "$(dirname "$dst")"
      cp "$src" "$dst"
      fixed=1
      actions+=("- Synced missing file: \`$rel\` -> \`$workdir\`")
    fi
  done
  if (( fixed == 1 )); then
    sync_fixes=$((sync_fixes + 1))
  fi
}

guard_state_file="$MAIN_ROOT/artifacts/devloop/resource_guard_state.txt"
guard_throttled="0"
if [[ -f "$guard_state_file" ]]; then
  guard_throttled="$(cat "$guard_state_file" 2>/dev/null || echo 0)"
fi

for row in "${LOOPS[@]}"; do
  IFS='|' read -r label workdir <<<"$row"
  status_file="$workdir/artifacts/devloop/status.txt"
  stop_file="$workdir/artifacts/devloop/STOP"
  log_file="$workdir/artifacts/devloop/continuous.log"

  sync_required_scripts "$workdir"

  # If secondary loop is paused while guard is not throttling, unpause and restart it.
  if [[ "$workdir" != "$MAIN_ROOT" && -f "$stop_file" && "$guard_throttled" != "1" ]]; then
    rm -f "$stop_file"
    unpause_fixes=$((unpause_fixes + 1))
    actions+=("- Cleared stale STOP file for \`$label\`")
    [[ "$AUTO_RESTART" == "1" ]] && restart_loop "$label"
  fi

  # Auto-fix known missing-script blocker from older worktrees.
  if [[ -f "$log_file" ]] && tail -n 200 "$log_file" | grep -q "can't open file .*scripts/enforce_layer1_focus.py"; then
    src="$MAIN_ROOT/scripts/enforce_layer1_focus.py"
    dst="$workdir/scripts/enforce_layer1_focus.py"
    if [[ -f "$src" ]]; then
      mkdir -p "$(dirname "$dst")"
      cp "$src" "$dst"
      sync_fixes=$((sync_fixes + 1))
      actions+=("- Repaired blocker \`enforce_layer1_focus.py\` in \`$workdir\`")
      [[ "$AUTO_RESTART" == "1" ]] && restart_loop "$label"
    fi
  fi

  # Restart stale/down loops.
  pid="$(get_pid "$label")"
  if [[ -z "$pid" ]]; then
    if [[ "$AUTO_RESTART" == "1" ]]; then
      restart_loop "$label"
      stale_fixes=$((stale_fixes + 1))
      actions+=("- Restarted down loop \`$label\`")
    fi
    continue
  fi

  if [[ -f "$status_file" ]]; then
    mod_epoch="$(stat -f %m "$status_file" 2>/dev/null || echo 0)"
    now_epoch="$(date +%s)"
    age="$((now_epoch - mod_epoch))"
    if (( age > MAX_STALE_SECONDS )) && [[ "$AUTO_RESTART" == "1" ]]; then
      restart_loop "$label"
      stale_fixes=$((stale_fixes + 1))
      actions+=("- Restarted stale loop \`$label\` (age=${age}s)")
    fi
  fi
done

{
  echo "# Devloop Self-Heal Report"
  echo
  echo "- Generated (UTC): \`$NOW_UTC\`"
  echo "- Guard throttled: \`$guard_throttled\`"
  echo "- Restart count: \`$restarts\`"
  echo "- Missing-file repairs: \`$sync_fixes\`"
  echo "- STOP repairs: \`$unpause_fixes\`"
  echo "- Stale/down repairs: \`$stale_fixes\`"
  echo
  echo "## Actions"
  if ((${#actions[@]} == 0)); then
    echo "- No repairs needed."
  else
    printf "%s\n" "${actions[@]}"
  fi
} >"$OUT_MD"

echo "restarts=$restarts sync_fixes=$sync_fixes unpause_fixes=$unpause_fixes stale_fixes=$stale_fixes" >"$OUT_STATUS"
echo "ok: self-heal report updated -> $OUT_MD"
