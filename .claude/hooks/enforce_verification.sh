#!/bin/bash
#
# Claude Code UserPromptSubmit Hook - Enforce Chain-of-Verification
#
# This hook reminds Claude to VERIFY before making claims.
# Created Jan 5, 2026 after hallucination incident (said "tomorrow" on trading day)
#
# Based on Meta Research: Chain-of-Verification reduces hallucinations by 23%
# https://arxiv.org/abs/2309.11495
#

set -euo pipefail

# Get current date/time with PROOF
CURRENT_ET=$(TZ=America/New_York date '+%A, %B %d, %Y at %I:%M %p ET')
CURRENT_UTC=$(date -u '+%Y-%m-%d %H:%M:%S UTC')

cat <<EOF
═══════════════════════════════════════════════════════════
🔒 CHAIN-OF-VERIFICATION PROTOCOL ACTIVE
═══════════════════════════════════════════════════════════
📅 VERIFIED DATE: $CURRENT_ET
🌐 UTC: $CURRENT_UTC

⚠️  BEFORE ANY CLAIM, YOU MUST:
1. Run verification command (date, git status, ls, etc.)
2. Show command output as EVIDENCE
3. Only claim what evidence supports

❌ FORBIDDEN (causes hallucinations):
- Saying "tomorrow/yesterday" without running 'date'
- Claiming "done" without showing proof
- Asserting facts without evidence

✅ REQUIRED PHRASES:
- "Let me verify: [run command]"
- "Evidence shows: [command output]"
- "I need to check this first"

💡 When uncertain: Say "I don't know, let me verify"
═══════════════════════════════════════════════════════════
EOF

exit 0
