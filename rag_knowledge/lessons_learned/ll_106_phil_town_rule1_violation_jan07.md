# Lesson Learned: Phil Town Rule 1 Violation - Unprotected Positions Lost $93.69 (Jan 7, 2026)

## Date
2026-01-07

## Category
CRITICAL - Capital Protection Failure

## Summary
Paper trading account lost $93.69 today (-0.09%) despite having +$762 in unrealized option gains.
Root cause: Open positions have NO stop-loss protection. Market drift eroded gains.

## Evidence
- Daily P/L: -$93.69 (from Alpaca screenshot 9:52 AM ET)
- No trades executed today (last trade: Jan 6)
- Open positions unprotected:
  - SPY: +$266.34 unrealized (NO stop-loss)
  - INTC260109P00035000: +$159.00 (NO stop-loss)
  - SOFI260123P00024000: +$47.00 (NO stop-loss)
  - SPY260123P00660000: +$556.00 (NO stop-loss)

## Phil Town Rule 1 Analysis
> "Rule #1: Don't Lose Money. Rule #2: Don't Forget Rule #1."

We violated Rule 1 by:
1. Not setting stop-losses on winning positions
2. Allowing market drift to erode unrealized gains
3. Having no automated protection mechanism

## Root Cause
- Trading system executes trades but does NOT manage existing positions
- No trailing stop-loss logic implemented
- No position monitoring during market hours

## Required Fix
1. Add trailing stop-loss orders to all open positions
2. Protect at least 50% of unrealized gains
3. Automate position management in daily-trading workflow

## Prevention Checklist
- [x] Implement `manage_open_positions()` function → `scripts/manage_positions.py`
- [x] Add trailing stop at 10% below current price for winners → `scripts/set_trailing_stops.py`
- [x] Add hard stop at -20% for losers (per system_state.json risk_rules)
- [x] CI workflow tasks: `set-trailing-stops` and `manage-positions`

## FIX APPLIED (Jan 7, 2026)

**Branch**: `claude/review-investment-strategy-WLpvw`
**Commit**: `b891dda`

### New Files Created:
1. `scripts/set_trailing_stops.py` - Sets trailing stop orders on ALL positions
2. `tests/test_set_trailing_stops.py` - 100% test coverage
3. Updated `.github/workflows/claude-agent-utility.yml` with new tasks

### Trailing Stop Configuration:
| Asset Type | Trailing Stop % |
|------------|-----------------|
| Equities | 10% |
| Options | 20% |

### To Activate Protection:
1. Merge PR to main
2. Trigger CI: `task=set-trailing-stops`

## CEO Directive
"Losing money is NOT allowed" - CLAUDE.md ABSOLUTE MANDATE

## Lesson
**A trade without a stop-loss is a hope, not a strategy.**
