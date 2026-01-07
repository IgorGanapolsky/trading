# Lesson Learned #110: Trailing Stops Script Existed But Never Executed

**ID**: LL-110
**Date**: January 7, 2026
**Severity**: CRITICAL
**Category**: Risk Management, Phil Town Rule #1

## The Issue

Paper account had **$1,113 in unrealized profits UNPROTECTED** because:
1. `scripts/set_trailing_stops.py` was created on Jan 7, 2026
2. The script was NEVER executed
3. The daily-trading.yml workflow had NO step to set trailing stops

## Evidence

```json
// From data/system_state.json - Open positions without protection
{
  "symbol": "INTC260109P00035000",
  "unrealized_pl": 151.0
},
{
  "symbol": "SOFI260123P00024000",
  "unrealized_pl": 56.0
},
{
  "symbol": "AMD260116P00200000",
  "unrealized_pl": 457.0
},
{
  "symbol": "SPY260123P00660000",
  "unrealized_pl": 449.0
}
// Total: $1,113 in profits at risk of evaporating
```

## Root Cause

**Script existed but was not integrated into workflow.**

The `set_trailing_stops.py` script was available in:
- `scripts/set_trailing_stops.py` (standalone script)
- `claude-agent-utility.yml` (manual trigger only)

But it was NOT in the **daily-trading.yml** workflow, which means:
- Positions were never automatically protected
- Manual intervention required every time
- One market gap could wipe out all profits

## Fix Applied

Added automatic trailing stop step to `daily-trading.yml`:

```yaml
- name: Set Trailing Stop-Loss Orders (Phil Town Rule 1)
  if: success()
  env:
    ALPACA_API_KEY: ${{ secrets.ALPACA_PAPER_KEY }}
    ALPACA_SECRET_KEY: ${{ secrets.ALPACA_PAPER_SECRET }}
  run: |
    python3 scripts/set_trailing_stops.py
```

## Phil Town Compliance

**Rule #1**: Don't lose money
**Rule #2**: Don't forget Rule #1

Our system was VIOLATING both rules by:
- Having profits but not protecting them
- Relying on hope instead of stop-losses

## Key Insight

**Infrastructure without automation is worthless.**

Having a script that CAN set trailing stops is meaningless if:
- It requires manual execution
- It's not in the daily workflow
- No one remembers to run it

## Prevention

1. Every risk protection script MUST be in automated workflow
2. After creating any new risk management tool, immediately integrate into CI
3. Add verification step to check trailing_stops section in system_state.json

## Tags

trailing_stops, risk_management, phil_town, rule_1, automation_gap, ci_integration
