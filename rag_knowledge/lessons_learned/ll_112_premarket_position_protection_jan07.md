# Lesson Learned #112: Pre-Market Position Protection Gap

**Date**: January 7, 2026
**Severity**: CRITICAL
**Category**: Risk Management, Phil Town Rule #1

## What Happened

CEO review revealed 5 open positions with $1,187.60 in unrealized gains had **ZERO PROTECTION**:

| Position | Unrealized P/L | Stop-Loss |
|----------|----------------|-----------|
| SPY | +$74.60 | NONE |
| INTC260109P00035000 | +$151.00 | NONE |
| SOFI260123P00024000 | +$56.00 | NONE |
| AMD260116P00200000 | +$457.00 | NONE |
| SPY260123P00660000 | +$449.00 | NONE |

## Root Cause

The `daily-trading.yml` workflow only set trailing stops **AFTER** trading activity.
On days with no new trades, existing positions remained unprotected.

## Evidence

```bash
$ python3 -c "import json; print(json.load(open('data/system_state.json')).get('trailing_stops', 'NOT CONFIGURED'))"
NOT CONFIGURED
```

## Fix Applied

Added `protect-existing-positions` job to `daily-trading.yml` that runs:
- **BEFORE** any new trades (`needs: [validate-and-test]`)
- At start of each trading day
- Sets trailing stops on ALL existing positions

Configuration:
- Equities: 10% trailing stop
- Options: 20% trailing stop (more volatile)

## Prevention

1. Session Start Checklist now includes position protection check
2. Workflow runs protection BEFORE trading, not just after
3. Added deferred item for manual trigger if needed

## Phil Town Rule #1

> "Rule #1: Don't Lose Money. Rule #2: Don't Forget Rule #1."

A trade without a stop-loss is a hope, not a strategy.

## Tags

trailing-stops, risk-management, phil-town, position-protection, premarket
