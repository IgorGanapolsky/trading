#!/usr/bin/env bash
set -euo pipefail

# Cron-friendly wrapper for worktree hygiene.
# Prunes stale entries and removes detached worktrees safely on a schedule.
#
# Suggested cron (weekly, Sunday 3:15am):
# 15 3 * * Sun cd /Users/ganapolsky_i/workspace/git/igor/trading && scripts/worktree_hygiene_cron.sh >> logs/worktree_hygiene.log 2>&1

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

LOG_FILE=${LOG_FILE:-"$repo_root/logs/worktree_hygiene.log"}
mkdir -p "$(dirname "$LOG_FILE")"

timestamp() { date '+%Y-%m-%d %H:%M:%S'; }

rotate_logs() {
  local max=10
  for ((i=max; i>=1; i--)); do
    if [[ -f "${LOG_FILE}.${i}" ]]; then
      local next=$((i+1))
      if (( next > max )); then
        rm -f "${LOG_FILE}.${i}"
      else
        mv "${LOG_FILE}.${i}" "${LOG_FILE}.${next}"
      fi
    fi
  done
  if [[ -f "$LOG_FILE" ]]; then
    mv "$LOG_FILE" "${LOG_FILE}.1"
  fi
}

rotate_logs

{
  echo "[$(timestamp)] 🔄 Worktree hygiene start (cron mode)"
  scripts/worktree_hygiene.sh --prune
  scripts/worktree_hygiene.sh --remove-detached
  echo "[$(timestamp)] ✅ Worktree hygiene complete"
} >> "$LOG_FILE" 2>&1
