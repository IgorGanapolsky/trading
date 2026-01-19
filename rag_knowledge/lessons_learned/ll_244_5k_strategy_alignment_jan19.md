# LL-244: 5K vs 100K Performance Gap Analysis

**Date**: 2026-01-19
**Severity**: HIGH
**Category**: Strategy Post-Mortem

## Summary
Analyzed why $5K account is losing while $100K account was profitable.

## Root Cause
We ignored what worked. The $100K account used:
1. SPY/AMD focus (high liquidity ETFs)
2. Iron condors (defined risk on BOTH sides)
3. Reasonable position sizing

The $5K account violated all of this:
1. Traded SOFI instead of SPY
2. Used naked puts instead of spreads
3. 96% position size on single trade

## Fix Applied
Updated trading_thresholds.py to enforce CLAUDE.md strategy:
- CSP_WATCHLIST = ["SPY"] (removed IWM)
- Added IRON_CONDOR_MIN_DTE = 30, MAX_DTE = 45
- Added EXIT_AT_DTE = 21 (avoid gamma risk)
- Added iron condor delta thresholds (15-20 delta)

## Lesson
Execute what already worked. The $100K success was with SPY iron condors - replicate it exactly.

## Tags
strategy, post-mortem, 5k-account, iron-condors, claude-md-compliance
