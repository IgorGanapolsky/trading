#!/usr/bin/env bash
set -euo pipefail

# Install or reload the worktree hygiene launchd job on macOS.
# Usage: scripts/install_worktree_launchd.sh

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
plist_src="$repo_root/scripts/launchd/com.trading.worktreehygiene.plist"
plist_dst="$HOME/Library/LaunchAgents/com.trading.worktreehygiene.plist"
log_path="$HOME/Library/Logs/worktree_hygiene.log"

mkdir -p "$(dirname "$plist_dst")" "$(dirname "$log_path")"

sed \
  -e "s#__REPO_PATH__#$repo_root#g" \
  -e "s#__LOG_PATH__#$log_path#g" \
  "$plist_src" > "$plist_dst"

launchctl unload "$plist_dst" >/dev/null 2>&1 || true
launchctl load "$plist_dst"
launchctl list | grep worktreehygiene || true

echo "✅ launchd job installed. Log: $log_path"
