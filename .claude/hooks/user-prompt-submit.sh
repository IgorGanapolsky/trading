#!/usr/bin/env bash
# Thin feedback detector that routes thumbs signals into the gateway hook helper.

set -euo pipefail

USER_MESSAGE="$(cat)"

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

printf '%s' "${USER_MESSAGE}" | python3 scripts/capture_hook_feedback.py >/dev/null 2>&1 || true

exit 0
