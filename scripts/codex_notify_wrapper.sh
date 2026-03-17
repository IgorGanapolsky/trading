#!/usr/bin/env bash
# Fan out Codex notify payload to OMX hook + repo feedback bridge.

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OMX_NOTIFY_HOOK="/opt/homebrew/lib/node_modules/oh-my-codex/scripts/notify-hook.js"

if [ -f "$OMX_NOTIFY_HOOK" ]; then
  node "$OMX_NOTIFY_HOOK" "$@" >/dev/null 2>&1 || true
fi

python3 -m src.learning.codex_feedback_bridge "$@" >/dev/null 2>&1 || true

exit 0
