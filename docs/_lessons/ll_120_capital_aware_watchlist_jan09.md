---
layout: post
title: "Lesson Learned #120: Capital-Aware Watchlist Required for Paper Trading"
date: 2026-01-09
---

# Lesson Learned #120: Capital-Aware Watchlist Required for Paper Trading

**Date**: January 9, 2026
**Category**: Trading Execution
**Severity**: CRITICAL
**Status**: RESOLVED

## Summary

Paper trading system was completely dormant for 3 days (Jan 7-9, 2026) despite having $5,000 in buying power. Root cause: Phil Town strategy watchlist contained only expensive stocks (AAPL, MSFT, GOOGL, etc.) that required $9,000-$90,000 collateral per CSP, far exceeding the $5,000 account size.

## Problem

- Paper account: $5,000 buying power
- Phil Town watchlist: AAPL, MSFT, V, MA, COST (all expensive stocks)
- CSP collateral required for AAPL at ~$93 MOS: $9,300
- Result: 100% of stocks filtered out → 0 trades for 3 days

## Root Cause

The Phil Town strategy was designed for a $100,000 paper account but the account was reset to $5,000 on Jan 7. The watchlist was never updated to match the new capital level.

**Code location**: `src/strategies/rule_one_options.py` line 241-258

## Solution Applied

1. **Reordered DEFAULT_UNIVERSE** by affordability:
   - TIER 1 ($5K): F, SOFI, T, INTC, BAC, VZ (strikes <= $50)
   - TIER 2 ($10K): KO, PG, JNJ, HD, MCD
   - TIER 3 ($20K+): AAPL, MSFT, GOOGL, AMZN, etc.

2. **Added capital-aware filter** in `find_put_opportunities()`:
   ```python
   required_collateral = target_strike * 100
   if required_collateral > cash_available:
       logger.debug(f"{symbol}: Strike ${target_strike:.2f} requires ${required_collateral:.0f} - SKIPPING")
       continue
   ```

3. **Updated system_state.json** with affordable watchlist

## Capital Tiers Reference

| Account Size | Max Strike | Example Stocks |
|-------------|-----------|----------------|
| $5,000 | $50 | F, SOFI, T, INTC, BAC |
| $10,000 | $100 | + KO, PG |
| $20,000 | $200 | + AAPL, NVDA, GOOGL |
| $50,000 | $500 | + MA, UNH, BRK-B |
| $100,000 | $1,000 | Full universe |

## Prevention

- **Always validate watchlist vs capital** when account size changes
- **Capital-aware filtering** should be standard in all options strategies
- **System health check** should verify at least 3 stocks in universe are affordable

## Related

- PR #1322: Stop paper trading losses - Rule #1 compliance
- LL-111: Paper capital must match real
- system_state.json: paper_account.valid_strategies

## Tags

`paper-trading` `options` `capital-management` `watchlist` `critical`
