# LL-246: 30% Portfolio Risk Violation Discovered

**Date**: 2026-01-20
**Severity**: CRITICAL
**Category**: Risk Management

## Summary

Discovered that current portfolio has 30% risk exposure when CLAUDE.md allows only 5% per position and 1 iron condor at a time.

## Evidence

```
Current positions:
- 3 bull put spreads (565/570, 595/600, 653/658)
- Each spread: $5-wide = $500 max loss
- Total max loss: $1,500
- Portfolio: $4,986.39
- Risk %: 30.1%

CLAUDE.md requires:
- Position limit: 1 iron condor at a time
- 5% max risk = $248
```

## Root Cause

The trade gateway was checking individual trade risk (5% per trade) but NOT:
1. Total number of open positions
2. Total portfolio risk across all positions

This allowed the system to open multiple positions that individually passed the 5% check but collectively exceeded safe limits.

## Fix Applied

Added two new checks to `src/risk/trade_gateway.py`:

1. **CHECK 0.7: MAX_POSITIONS_EXCEEDED**
   - Blocks new trades if already have 1+ spreads open
   - Per CLAUDE.md: "1 iron condor at a time"

2. **CHECK 0.8: TOTAL_PORTFOLIO_RISK_EXCEEDED**
   - Blocks new trades if total portfolio risk > 15%
   - Calculated by summing max loss of all open spreads

## New Rejection Reasons

```python
MAX_POSITIONS_EXCEEDED = "Maximum open positions exceeded - 1 iron condor at a time per CLAUDE.md"
TOTAL_PORTFOLIO_RISK_EXCEEDED = "Total portfolio risk exceeds 15% - close positions before opening new"
```

## Lesson Learned

Individual trade checks are not sufficient. Must also validate:
- Total open position count
- Aggregate portfolio risk

The system should have blocked trades 2 and 3 since trade 1 was already open.

## Action Items

- [x] Add position count check to gateway
- [x] Add total risk check to gateway
- [ ] Consider workflow to alert when over-exposed
- [ ] Review how 3 positions got opened (audit trail)

## Tags

risk-management, position-sizing, phil-town-rule-one, critical, violation
