#!/bin/bash
# HARD BLOCK: CTO cannot close positions
# Only iron-condor-guardian.yml workflow can close positions
# Per LL-306, LL-325: "Trust the guardrails, not the agent"

INPUT="$1"

# Block ANY position closing attempt
if echo "${INPUT}" | grep -qiE "(close_position|close.*position|submit_order.*SELL|submit_order.*BUY.*close|liquidat)"; then
	echo "🚫 HARD BLOCK: Position closing disabled for CTO"
	echo ""
	echo "Only the iron-condor-guardian workflow can close positions."
	echo "This is enforced by LL-306 and LL-325."
	echo ""
	echo "Guardian closes automatically when:"
	echo "  - 50% profit reached"
	echo "  - 200% stop loss hit"
	echo "  - 7 DTE reached"
	echo ""
	echo "You cannot override this. Phil Town Rule #1."
	exit 1
fi

# Block removal OR rename/copy of the TRADING_HALTED kill-switch file via shell.
# It is read by src/risk/trade_gateway.py; removing it (or moving it to a
# sibling like data/TRADING_HALTED.bak) re-enables trading.
#
# The Crisis Monitor process auto-clears it when there are zero positions
# (src/safety/crisis_monitor.py) — that path does not go through this hook.
#
# Defense-in-depth: in the May 29, 2026 session, `data/TRADING_HALTED` was
# silently renamed to `data/TRADING_HALTED.bak`. The original guard caught
# `rm`, `mv`-to-elsewhere, and `> path` redirection, but NOT a rename to a
# sibling. This guard widens the net: any of (mv|cp|rename|os.rename|
# Path.rename|shutil.move) combined with a TRADING_HALTED token denies,
# regardless of destination suffix.
MAGIC_WORD_FILE="/tmp/claude_magic_word_authorized"

if echo "${INPUT}" | grep -qE '(data/TRADING_HALTED|data/SYSTEM_HALTED|data/trading_halt\.txt|\bTRADING_HALTED\b)' &&
	echo "${INPUT}" | grep -qE '(\b(rm|mv|cp|unlink|truncate|rename|shutil\.move|os\.rename|Path\.rename)\b|>\s*data/TRADING_HALTED|>\s*data/SYSTEM_HALTED|>\s*data/trading_halt)'; then
	if [[ -f ${MAGIC_WORD_FILE} ]]; then
		rm -f "${MAGIC_WORD_FILE}"
		exit 0
	fi
	echo "🚫 HARD BLOCK: Remove/rename/copy of trading halt file via shell"
	echo ""
	echo "data/TRADING_HALTED is a load-bearing kill-switch read by"
	echo "src/risk/trade_gateway.py. Removing it — OR renaming it to a"
	echo "sibling like data/TRADING_HALTED.bak — re-enables trade execution."
	echo ""
	echo "Caught operators: rm, mv (incl. rename-to-sibling), cp, unlink,"
	echo "truncate, rename, os.rename, Path.rename, shutil.move, > redirect."
	echo ""
	echo "If clearing is intended, do it through crisis_monitor's"
	echo "auto-clear path (zero positions) or explicit CEO override:"
	echo "  touch /tmp/claude_magic_word_authorized && rm data/TRADING_HALTED"
	echo ""
	echo "Boundary policy: .claude/rules/boundary-policy.md Hard Block #2"
	exit 1
fi
exit 0
