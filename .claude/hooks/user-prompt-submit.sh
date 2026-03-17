#!/usr/bin/env bash
# Thin feedback detector that routes thumbs signals into the shared gateway bridge.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

USER_MESSAGE="$(cat)"

get_last_claude_response() {
  local transcript_dir="${HOME}/.claude/projects"
  local latest_transcript
  latest_transcript="$(find "${transcript_dir}" -name "*.jsonl" -type f -print0 2>/dev/null | xargs -0 ls -t 2>/dev/null | head -1)"
  if [[ -n "${latest_transcript}" && -f "${latest_transcript}" ]]; then
    tail -50 "${latest_transcript}" 2>/dev/null \
      | grep '"type":"assistant"' \
      | tail -1 \
      | python3 -c '
import json
import sys

try:
    line = sys.stdin.read().strip()
    if line:
        obj = json.loads(line)
        msg = obj.get("message", {})
        content = msg.get("content", [])
        text_parts = [c.get("text", "") for c in content if c.get("type") == "text"]
        print(" ".join(text_parts)[:500])
except Exception:
    pass
' 2>/dev/null || true
  fi
}

detect_feedback() {
  local msg_lower
  msg_lower="$(printf '%s' "${USER_MESSAGE}" | tr '[:upper:]' '[:lower:]')"
  if printf '%s' "${msg_lower}" | grep -qE "thumbs down|👎|bad response|wrong answer|incorrect"; then
    printf 'negative\n'
    return 0
  fi
  if printf '%s' "${msg_lower}" | grep -qE "thumbs up|👍|great|good job|well done|perfect|excellent"; then
    printf 'positive\n'
    return 0
  fi
  printf 'none\n'
}

LAST_CLAUDE_RESPONSE="$(get_last_claude_response)"
FEEDBACK_TYPE="$(detect_feedback)"

if [[ "${FEEDBACK_TYPE}" == "none" ]]; then
  exit 0
fi

if [[ "${FEEDBACK_TYPE}" == "negative" ]]; then
  printf '\n'
  printf '==================================================\n'
  printf 'THUMBS DOWN DETECTED - RECORDING VIA GATEWAY\n'
  printf '==================================================\n'
  printf '\n'
else
  printf '\n'
  printf '==================================================\n'
  printf 'THUMBS UP DETECTED - RECORDING VIA GATEWAY\n'
  printf '==================================================\n'
  printf '\n'
fi

PAYLOAD="$(python3 - "${PROJECT_ROOT}" "${USER_MESSAGE}" "${LAST_CLAUDE_RESPONSE}" <<'PY'
import json
import sys
from datetime import datetime, timezone

project_root = sys.argv[1]
user_message = sys.argv[2]
assistant_message = sys.argv[3]
payload = {
    "cwd": project_root,
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "turn_id": datetime.now(timezone.utc).strftime("hook-%Y%m%d%H%M%S%f"),
    "input-messages": [user_message],
    "last-assistant-message": assistant_message,
}
print(json.dumps(payload))
PY
)"

(cd "${PROJECT_ROOT}" && python3 -m src.learning.codex_feedback_bridge "${PAYLOAD}") >/dev/null 2>&1 || true

exit 0
