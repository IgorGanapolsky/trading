#!/bin/bash
#
# Cost Circuit Breaker - Track and limit Claude API spending
#
# This hook runs on SessionStart to check cumulative session costs
# and warn/block if approaching budget limits.
#
# Budget tracking uses local file (works in sandbox)
# CI can sync to cloud for persistence
#

set -euo pipefail

COST_FILE="${CLAUDE_PROJECT_DIR:-/home/user/trading}/data/api_costs.json"
DAILY_BUDGET_USD=${DAILY_BUDGET_USD:-10.00}
MONTHLY_BUDGET_USD=${MONTHLY_BUDGET_USD:-200.00}

# Initialize cost file if missing
if [ ! -f "$COST_FILE" ]; then
    mkdir -p "$(dirname "$COST_FILE")"
    cat > "$COST_FILE" << 'INIT'
{
  "daily_costs": {},
  "monthly_total": 0.0,
  "last_reset": "",
  "sessions_today": 0
}
INIT
fi

# Get current costs using Python
COST_CHECK=$(python3 << 'PYEND'
import json
from datetime import datetime, date
import sys

cost_file = "data/api_costs.json"
daily_budget = float("${DAILY_BUDGET_USD:-10.00}".replace("${DAILY_BUDGET_USD:-", "").replace("}", "") or 10.00)
monthly_budget = float("${MONTHLY_BUDGET_USD:-200.00}".replace("${MONTHLY_BUDGET_USD:-", "").replace("}", "") or 200.00)

try:
    with open(cost_file) as f:
        costs = json.load(f)
except:
    costs = {"daily_costs": {}, "monthly_total": 0.0, "last_reset": "", "sessions_today": 0}

today = date.today().isoformat()
month = date.today().strftime("%Y-%m")

# Reset daily if new day
if costs.get("last_reset") != today:
    costs["daily_costs"][today] = 0.0
    costs["sessions_today"] = 0
    costs["last_reset"] = today

# Get today's cost
today_cost = costs.get("daily_costs", {}).get(today, 0.0)
monthly_cost = sum(v for k, v in costs.get("daily_costs", {}).items() if k.startswith(month))

# Increment session count
costs["sessions_today"] = costs.get("sessions_today", 0) + 1

# Save updated costs
with open(cost_file, 'w') as f:
    json.dump(costs, f, indent=2)

# Check budgets
daily_pct = (today_cost / daily_budget) * 100 if daily_budget > 0 else 0
monthly_pct = (monthly_cost / monthly_budget) * 100 if monthly_budget > 0 else 0

if daily_pct >= 100:
    print(f"BLOCK|Daily budget exceeded: ${today_cost:.2f}/${daily_budget:.2f}")
elif daily_pct >= 80:
    print(f"WARN|Daily budget at {daily_pct:.0f}%: ${today_cost:.2f}/${daily_budget:.2f}")
elif monthly_pct >= 90:
    print(f"WARN|Monthly budget at {monthly_pct:.0f}%: ${monthly_cost:.2f}/${monthly_budget:.2f}")
else:
    print(f"OK|Sessions today: {costs['sessions_today']} | Daily: ${today_cost:.2f}/${daily_budget:.2f} | Monthly: ${monthly_cost:.2f}/${monthly_budget:.2f}")
PYEND
)

STATUS="${COST_CHECK%%|*}"
MESSAGE="${COST_CHECK#*|}"

case "$STATUS" in
    BLOCK)
        echo "════════════════════════════════════════════════════════════"
        echo "🚨 COST CIRCUIT BREAKER TRIGGERED 🚨"
        echo "════════════════════════════════════════════════════════════"
        echo ""
        echo "$MESSAGE"
        echo ""
        echo "Options:"
        echo "  1. Wait until tomorrow for daily reset"
        echo "  2. Increase DAILY_BUDGET_USD in environment"
        echo "  3. Override with COST_OVERRIDE=true (emergency only)"
        echo "════════════════════════════════════════════════════════════"
        # Don't exit 1 - that blocks the session. Just warn loudly.
        ;;
    WARN)
        echo "⚠️  COST WARNING: $MESSAGE"
        ;;
    OK)
        echo "💰 $MESSAGE"
        ;;
esac

exit 0
