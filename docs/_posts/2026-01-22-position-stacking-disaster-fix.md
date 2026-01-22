---
layout: post
title: "LL-275: The Position Stacking Disaster and How We Fixed It"
date: 2026-01-22
categories: [lessons-learned, trading, safety]
tags: [bug-fix, risk-management, options, iron-condor]
---

# LL-275: The Position Stacking Disaster

## What Happened

On January 22, 2026, we discovered a critical bug in our trading safety gate that allowed unlimited contracts to accumulate in the same symbol. The result: **8 long contracts of SPY260220P00658000** with a **-$1,472 unrealized loss**.

## Root Cause Analysis

The `mandatory_trade_gate.py` CHECK 2.5 was supposed to enforce "1 iron condor at a time" (4 positions max). However, it only counted **unique symbols**, not **total contracts**.

```python
# THE BUG - Only counted unique positions
MAX_POSITIONS = 4  # 1 iron condor = 4 legs
current_position_count = len(current_positions)  # Counts unique symbols!

if side == "BUY" and current_position_count >= MAX_POSITIONS:
    # Block...
```

This allowed:
- Day 1: Buy 1 contract of 658 put → 1 position → PASS
- Day 2: Buy 1 more of same symbol → still 1 position → PASS
- Day 3: Buy 1 more → still 1 position → PASS
- ...repeated until 8 contracts accumulated

## The Trade History Evidence

```
SPY260220P00658000 TRADES:
- BUY 1 contract (x9 separate trades)
- SELL 1 contract (x1 trade)
- Net: 8 long contracts at -$1,472 loss
```

## The Fix (CHECK 2.6)

Added position stacking prevention that blocks buying more of an existing symbol:

```python
# CHECK 2.6: Position STACKING prevention (Jan 22, 2026 - LL-275)
if side == "BUY" and current_positions:
    existing_symbols = [p.get("symbol", "") for p in current_positions]
    if symbol in existing_symbols:
        return GateResult(
            approved=False,
            reason=f"POSITION STACKING BLOCKED: Already hold contracts of {symbol}",
        )
```

## Two-Layer Defense

We now have prevention AND detection:

| Layer | File | Action |
|-------|------|--------|
| PREVENTION | `mandatory_trade_gate.py` | Blocks buying existing symbols |
| DETECTION | `detect-contract-accumulation.yml` | Alerts every 15 min if >2 contracts |

## Tests Added

- `test_position_stacking_blocked` - verifies buying existing symbol is blocked
- `test_sell_existing_position_allowed` - verifies selling is still allowed

## Lessons Learned

1. **Count contracts, not just symbols** - A single symbol can hide unlimited risk
2. **Prevention > Detection** - By the time detection fires, trades are already made
3. **Test edge cases** - The gate passed all tests but had this fatal flaw
4. **Two-layer defense** - Always have a backup monitoring system

## Status

- **Fix deployed**: PR #2702 merged (SHA: bf253af)
- **Tests**: 878 passed
- **CI**: Passing
- **Position**: Still blocked by PDT until tomorrow

---

*This lesson cost $1,472 in paper trading. The real value is ensuring it never happens with real money.*
