---
layout: post
title: "Lesson Learned: CSP Script Was Buying Shares Instead of Selling Puts"
date: 2026-01-06
---

# Lesson Learned: CSP Script Was Buying Shares Instead of Selling Puts

**ID**: LL-089
**Date**: 2026-01-06
**Severity**: CRITICAL
**Category**: code_bug, trading_execution

## Incident

The `simple_daily_trader.py` script claimed to execute "Cash-Secured Puts" but was actually buying SPY shares. This caused the system to miss the $100/day North Star goal because no premium was being collected.

## Root Cause

Lines 232-241 in `simple_daily_trader.py` had:
```python
# First try: buy SPY shares (guaranteed to work)
order_request = MarketOrderRequest(
    symbol="SPY",
    qty=1,  # Buy 1 share of SPY
    side=OrderSide.BUY,
    ...
)
```

The code said "Cash-Secured Put" in comments but executed EQUITY BUYS.

## Impact

- System was not following Phil Town's Rule #1 strategy
- No options premium was being collected
- $100/day North Star goal was unreachable
- Paper trading showed only equity P/L, not theta decay income

## Fix Applied

Changed `execute_cash_secured_put()` to actually:
1. Query Alpaca options chain for real contracts
2. SELL TO OPEN put options (not buy shares)
3. Use proper collateral calculation (~$57k for 1 SPY CSP)
4. Include Phil Town reference in trade metadata

## Prevention

1. **Code Review**: Function names must match behavior
2. **Integration Tests**: Test that CSP functions actually sell options
3. **Trade Logging**: Log trade TYPE (equity vs options) to catch mismatches
4. **Daily Audit**: Verify trades match strategy intent

## Tags

`cash-secured-put`, `options`, `phil-town`, `code-bug`, `critical`
