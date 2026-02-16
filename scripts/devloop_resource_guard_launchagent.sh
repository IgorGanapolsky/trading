#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="${LABEL:-com.joeyrahme.trading.devloop.guard}"
PLIST_PATH="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$REPO_ROOT/artifacts/devloop"
OUT_LOG="$LOG_DIR/resource_guard.out.log"
ERR_LOG="$LOG_DIR/resource_guard.err.log"

CHECK_INTERVAL_SECONDS_VALUE="${CHECK_INTERVAL_SECONDS:-20}"
HIGH_LOAD_VALUE="${HIGH_LOAD:-12.0}"
LOW_LOAD_VALUE="${LOW_LOAD:-8.0}"
MIN_FREE_GB_VALUE="${MIN_FREE_GB:-0.8}"
RECOVER_FREE_GB_VALUE="${RECOVER_FREE_GB:-1.5}"
STOP_FILES_CSV_VALUE="${STOP_FILES_CSV:-/Users/joeyrahme/GitHubWorkspace/trading-strategy-loop/artifacts/devloop/STOP,/Users/joeyrahme/GitHubWorkspace/trading-tetrate-loop/artifacts/devloop/STOP,/Users/joeyrahme/GitHubWorkspace/trading-evidence-loop/artifacts/devloop/STOP}"

mkdir -p "$LOG_DIR" "$HOME/Library/LaunchAgents"

install_agent() {
  cat >"$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>

  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>-lc</string>
    <string>cd "$REPO_ROOT" &amp;&amp; ./scripts/devloop_resource_guard.sh</string>
  </array>

  <key>WorkingDirectory</key>
  <string>$REPO_ROOT</string>

  <key>EnvironmentVariables</key>
  <dict>
    <key>CHECK_INTERVAL_SECONDS</key>
    <string>$CHECK_INTERVAL_SECONDS_VALUE</string>
    <key>HIGH_LOAD</key>
    <string>$HIGH_LOAD_VALUE</string>
    <key>LOW_LOAD</key>
    <string>$LOW_LOAD_VALUE</string>
    <key>MIN_FREE_GB</key>
    <string>$MIN_FREE_GB_VALUE</string>
    <key>RECOVER_FREE_GB</key>
    <string>$RECOVER_FREE_GB_VALUE</string>
    <key>STOP_FILES_CSV</key>
    <string>$STOP_FILES_CSV_VALUE</string>
    <key>PATH</key>
    <string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>

  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>

  <key>StandardOutPath</key>
  <string>$OUT_LOG</string>
  <key>StandardErrorPath</key>
  <string>$ERR_LOG</string>
</dict>
</plist>
EOF

  launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"
  launchctl enable "gui/$(id -u)/$LABEL" || true
  launchctl kickstart -k "gui/$(id -u)/$LABEL"

  echo "installed: $PLIST_PATH"
  echo "label: $LABEL"
}

uninstall_agent() {
  launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
  rm -f "$PLIST_PATH"
  echo "uninstalled: $LABEL"
}

status_agent() {
  echo "plist: $PLIST_PATH"
  [[ -f "$PLIST_PATH" ]] && echo "plist_present=yes" || echo "plist_present=no"
  launchctl print "gui/$(id -u)/$LABEL" 2>/dev/null | sed -n '1,40p' || echo "launchd_status=not_loaded"
  echo "stdout_log: $OUT_LOG"
  echo "stderr_log: $ERR_LOG"
}

case "${1:-}" in
  install) install_agent ;;
  uninstall) uninstall_agent ;;
  status) status_agent ;;
  restart)
    uninstall_agent
    install_agent
    ;;
  *)
    echo "Usage: $0 <install|uninstall|status|restart>"
    exit 1
    ;;
esac
