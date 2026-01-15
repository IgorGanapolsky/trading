# LL-206: Why $5K Account Failed - Complete Execution Failure Analysis

**Date:** January 15, 2026
**Severity:** CRITICAL
**Category:** post-mortem, strategy, execution

## Summary

The $5K paper trading account lost -$40.74 (-0.81%) due to three cascading execution failures over 76 days.

## Phase 1: 74 Days of Zero Trades (Nov 1 - Jan 12)

### Root Causes
| Blocker | Code Location | Impact |
|---------|---------------|--------|
| Wrong ticker | `guaranteed_trader.py` targeted SPY ($580) | Can't afford 100 shares |
| RSI gate | Required RSI < 30 OR > 70 | Blocked 95%+ opportunities |
| RAG gate | Queried "failures", blocked if found | Self-sabotage |
| Cash threshold | Required $5000 cash (line 300) | Any position = blocked |

**Result:** 74 days, ZERO profit, ZERO learning.

## Phase 2: Day 74 Emergency Fix (Jan 13)

### What Changed
- SPY → SOFI (affordable stock)
- Removed RSI/RAG gates
- "Buy $100 SOFI daily"

### What Was Missed
- SOFI earnings: Jan 30, 2026
- CLAUDE.md blackout: "SOFI: AVOID until Feb 1"
- Position size: 96% of portfolio (violated 5% rule)

## Phase 3: Blackout Violation & Force-Close (Jan 13-14)

### Timeline
| Date/Time | Event | Impact |
|-----------|-------|--------|
| Jan 13 9:35 AM | SOFI CSP opened during blackout | Violation |
| Jan 14 9:46 AM | Force-close triggered | -$18.31 options loss |
| Jan 14 EOD | Total daily loss | -$65.58 |

### Why Force-Close Was Correct
- Potential loss if held through earnings: -$4,800 (96% of portfolio)
- Actual loss taken: -$40.74 (0.81%)
- Phil Town Rule #1 saved by cutting early

## Comparison: $100K vs $5K Accounts

| $100K Account (Success) | $5K Account (Failure) |
|------------------------|----------------------|
| Human decisions | Automated with bad gates |
| SPY focus | SOFI desperation pick |
| Iron condors (defined risk) | Naked put (96% exposure) |
| No earnings conflicts | Traded INTO blackout |

## Key Lessons

1. **Over-engineering kills execution** - 74 days of zero trades
2. **Panic pivots break rules** - Picked SOFI without checking earnings
3. **Documentation ≠ enforcement** - CLAUDE.md rules weren't in code
4. **Defined risk mandatory** - Credit spreads, not naked positions
5. **Position sizing saves accounts** - 5% rule would have limited loss

## Prevention Going Forward

1. SPY/IWM ONLY - No individual stocks
2. Credit spreads - Defined risk
3. 5% max position - $248 max risk
4. Pre-trade checklist IN CODE - Automated enforcement
5. Earnings blackout check - Block trades automatically

## Tags

`execution-failure`, `post-mortem`, `over-engineering`, `blackout-violation`, `phil-town`, `rule-1`
