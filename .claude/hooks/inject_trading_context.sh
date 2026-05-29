#!/bin/bash
# Trading context injection hook
# Provides market hours, dates, and trading context to Claude sessions

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"

# All date/time operations use Eastern Time (trading timezone)
TODAY=$(TZ=America/New_York date +%Y-%m-%d)
FULL_DATE=$(TZ=America/New_York date "+%A, %B %d, %Y")
DAY_OF_WEEK=$(TZ=America/New_York date +%A)
DAY_NUM=$(TZ=America/New_York date +%u)
CURRENT_HOUR=$(TZ=America/New_York date +%H)
CURRENT_MIN=$(TZ=America/New_York date +%M)

# Weekend detection
IS_WEEKEND="false"
if [[ ${DAY_NUM} -ge 6 ]]; then
	IS_WEEKEND="true"
fi

# Market hours: 9:30 AM - 4:00 PM ET
MARKET_OPEN="false"
if [[ ${IS_WEEKEND} == "false" ]]; then
	if [[ ${CURRENT_HOUR} -ge 9 ]] && [[ ${CURRENT_HOUR} -lt 16 ]]; then
		if [[ ${CURRENT_HOUR} -eq 9 ]] && [[ ${CURRENT_MIN} -lt 30 ]]; then
			MARKET_OPEN="false"
		else
			MARKET_OPEN="true"
		fi
	fi
fi

# Calculate days since last system_state update.
# The state writer is the sync-alpaca-status.yml workflow on main, so the
# freshest copy lives on origin/main even when a working branch is stale.
# We compare the freshest of (local working tree, origin/main) so non-main
# branches don't false-alarm when main is being updated normally.
SYSTEM_STATE="${PROJECT_ROOT}/data/system_state.json"
get_days_old() {
	local update_str="$1"
	if [[ -z ${update_str} ]]; then
		echo 999
		return
	fi
	local last_ts
	last_ts=$(TZ=America/New_York date -j -f "%Y-%m-%d" "${update_str}" +%s 2>/dev/null || echo "")
	if [[ -z ${last_ts} ]]; then
		echo 999
		return
	fi
	local current_ts
	current_ts=$(TZ=America/New_York date +%s)
	echo $(((current_ts - last_ts) / 86400))
}

LOCAL_LAST_UPDATE=""
if [[ -f ${SYSTEM_STATE} ]]; then
	LOCAL_LAST_UPDATE=$(grep -o '"last_updated": "[^"]*"' "${SYSTEM_STATE}" | head -1 | cut -d'"' -f4 | cut -d'T' -f1 2>/dev/null || echo "")
fi
LOCAL_DAYS_OLD=$(get_days_old "${LOCAL_LAST_UPDATE}")

# Check origin/main as fallback (background-fetch first, ignore failures so the
# hook stays fast and offline-safe).
MAIN_DAYS_OLD=999
MAIN_LAST_UPDATE=""
if command -v git >/dev/null 2>&1 && git -C "${PROJECT_ROOT}" rev-parse --git-dir >/dev/null 2>&1; then
	git -C "${PROJECT_ROOT}" fetch --quiet origin main 2>/dev/null || true
	MAIN_LAST_UPDATE=$(git -C "${PROJECT_ROOT}" show origin/main:data/system_state.json 2>/dev/null | grep -o '"last_updated": "[^"]*"' | head -1 | cut -d'"' -f4 | cut -d'T' -f1 2>/dev/null || echo "")
	MAIN_DAYS_OLD=$(get_days_old "${MAIN_LAST_UPDATE}")
fi

# Use whichever is fresher.
DAYS_OLD=${LOCAL_DAYS_OLD}
if [[ ${MAIN_DAYS_OLD} -lt ${DAYS_OLD} ]]; then
	DAYS_OLD=${MAIN_DAYS_OLD}
fi

# Output trading context
echo "<trading-context>"
echo "Date: ${FULL_DATE}"
echo "Market Open: ${MARKET_OPEN}"
echo "Weekend: ${IS_WEEKEND}"
if [[ ${DAYS_OLD} -gt 1 ]]; then
	echo "WARNING: System state is ${DAYS_OLD} days old (run: git pull origin main, or python scripts/sync_alpaca_state.py)"
elif [[ ${LOCAL_DAYS_OLD} -gt 1 ]] && [[ ${MAIN_DAYS_OLD} -le 1 ]]; then
	echo "NOTE: local state lagging main by ${LOCAL_DAYS_OLD}d; origin/main is fresh"
fi
echo "</trading-context>"

# Export variables for potential downstream use
export TODAY FULL_DATE DAY_OF_WEEK MARKET_OPEN IS_WEEKEND

exit 0
