#!/usr/bin/env bash
set -euo pipefail

# Post the latest worktree hygiene result to Slack (or just print).
# Requires SLACK_WEBHOOK_URL env to send; otherwise prints to stdout.
#
# Usage:
#   LOG_FILE=logs/worktree_hygiene.log scripts/worktree_hygiene_digest.sh

LOG_FILE=${LOG_FILE:-"logs/worktree_hygiene.log"}
WEBHOOK=${SLACK_WEBHOOK_URL:-}
TAIL_LINES=${TAIL_LINES:-50}

if [[ ! -f "$LOG_FILE" ]]; then
  echo "Log file not found: $LOG_FILE"
  exit 1
fi

summary=$(tail -n "$TAIL_LINES" "$LOG_FILE")

if [[ -z "$WEBHOOK" ]]; then
  echo "SLACK_WEBHOOK_URL not set; printing summary:\n"
  echo "$summary"
  exit 0
fi

payload=$(jq -n --arg text "*Worktree hygiene digest*\\n\\n\`\`\`$summary\`\`\`" '{text: $text}')

curl -s -X POST -H 'Content-type: application/json' --data "$payload" "$WEBHOOK" >/dev/null
echo "Slack digest sent."
