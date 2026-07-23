#!/bin/bash
# MAGIC WORD REQUIRED: CEO must say "EXECUTE RULE1" for any destructive action
# This prevents CTO from acting impulsively

# Check conversation for magic word (passed via env or file)
MAGIC_WORD_FILE="/tmp/claude_magic_word_authorized"

# Destructive actions that require magic word
INPUT="$1"
if echo "$INPUT" | grep -qiE "(close|sell|liquidate|delete|remove|cancel.*order)"; then
	if [[ ! -f $MAGIC_WORD_FILE ]]; then
		{
			echo "🔐 MAGIC WORD REQUIRED"
			echo ""
			echo "CEO must say: EXECUTE RULE1"
			echo ""
			echo "This authorizes destructive actions for this session."
			echo "Without it, CTO cannot close positions, cancel orders, or delete anything."
		} >&2
		exit 2
	fi
fi
exit 0
