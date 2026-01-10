---
layout: post
title: "LL-095: Pre-Trade Pattern Validation Wired In"
date: 2026-01-07
---

# LL-095: Pre-Trade Pattern Validation Wired In

**Date**: January 7, 2026
**Severity**: CRITICAL
**Status**: FIXED

## Problem

TradeMemory.py existed with excellent pattern validation code but was **NEVER CALLED** from any execution path:
- `query_similar()` checks historical win rates before trading
- The code was designed to block trades with <50% historical win rate
- But `alpaca_executor.py` never imported or used it

**Result**: System was trading blindly without learning from history, leading to -3.04% average daily returns.

## Root Cause

TradeMemory.py was written during December 2025 research but never integrated:
1. Code in `/src/learning/trade_memory.py` - fully functional
2. Execution in `/src/execution/alpaca_executor.py` - never imported it
3. Gap: Writing to memory happened, but QUERYING before trades did not

## Solution

Added pre-trade pattern validation to `alpaca_executor.py:place_order()`:

```python
# Query TradeMemory BEFORE executing - learn from history
from src.learning.trade_memory import TradeMemory
memory = TradeMemory()
pattern_check = memory.query_similar(strategy, entry_reason)

if pattern_check.get("found") and sample_size >= 5 and win_rate < 0.50:
    raise TradeBlockedError(f"Pattern has {win_rate:.1%} win rate - below 50%")
```

## Changes Made

1. **alpaca_executor.py** (lines 406-448): Added pre-trade pattern validation
2. **test_alpaca_executor.py**: Added 4 new tests for pattern validation
3. This lesson learned

## Verification

Tests added:
- `test_pattern_check_blocks_losing_strategy` - blocks <50% win rate
- `test_pattern_check_allows_winning_strategy` - allows >60% win rate
- `test_pattern_check_allows_new_strategy` - allows no-history patterns
- `test_pattern_check_warns_marginal_strategy` - warns on 50-60%

## Impact

- **Before**: Trade blindly → lose money → record after
- **After**: Check history → only trade winning patterns → compound gains

This directly implements Phil Town Rule #1: "Don't Lose Money"

## Prevention

Before coding ANY trading feature, ask:
1. Does this QUERY history before acting?
2. Does this BLOCK losing patterns?
3. Is this wired into the ACTUAL execution path?

## Tags
- #critical
- #trade-execution
- #pattern-validation
- #rule-one
- #fixed
