---
layout: post
title: 'LL-275: Position Stacking Disaster and Fix'
date: 2026-01-22
last_modified_at: "2026-01-22"
categories:
- lessons-learned
- trading
- safety
tags:
- bug-fix
- risk-management
- options
- iron-condor
- self-healing
- ci-pipeline
- rlhf
description: A self-healing CI pipeline must include position stacking prevention
  at the code level.
image: "/assets/snapshots/progress_latest.png"

---

## Answer Block

> **Answer Block:** A self-healing CI pipeline must include position stacking prevention at the code level. Our safety gate counted unique symbols instead of total contracts, allowing 8 contracts to accumulate with a -$1,472 unrealized loss. The fix: block buying ANY additional contracts of an existing symbol, plus detection alerts every 15 minutes.

# LL-275: Self-Healing Trading System - Position Stacking Prevention

## What is position stacking in options trading?

> Position stacking occurs when a system allows multiple buy orders for the same symbol without checking existing holdings. This can concentrate risk beyond position limits. Our bug allowed 8 contracts of the same option to accumulate because the safety gate only counted unique symbols, not total contract quantity.

On January 22, 2026, we discovered a critical bug in our trading safety gate that allowed unlimited contracts to accumulate in the same symbol. The result: **8 long contracts of SPY260220P00658000** with a **-$1,472 unrealized loss**.

---

## How does position stacking bypass safety gates?

> Safety gates that count positions by unique symbol (not contract quantity) can be bypassed. If you own 1 contract of SPY puts, buying another contract of the SAME option still shows as "1 position" - the gate passes, and risk accumulates silently.

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

---

## What evidence shows position stacking in trade history?

> Trade history reveals stacking when you see multiple BUY orders for the same option symbol across different dates without corresponding SELL orders. Our history showed 9 separate BUY trades for the same 658 put, with only 1 SELL.

```
SPY260220P00658000 TRADES:
- BUY 1 contract (x9 separate trades)
- SELL 1 contract (x1 trade)
- Net: 8 long contracts at -$1,472 loss
```

---

## How do you implement position stacking prevention?

> Add a code check that blocks buying ANY contract of an already-held symbol. Query existing positions, extract symbols, and reject if the new order's symbol exists in holdings. This is CHECK 2.6 in our gate pipeline.

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

---

## What is two-layer defense for trading safety?

> Two-layer defense combines PREVENTION (code blocks bad trades before execution) with DETECTION (monitoring alerts if prevention fails). The detection layer is backup - if a bug bypasses prevention, you catch it within 15 minutes rather than days.

We now have prevention AND detection:

| Layer      | File                               | Action                              |
| ---------- | ---------------------------------- | ----------------------------------- |
| PREVENTION | `mandatory_trade_gate.py`          | Blocks buying existing symbols      |
| DETECTION  | `detect-contract-accumulation.yml` | Alerts every 15 min if >2 contracts |

---

## How do you test position stacking prevention?

> Write two tests: (1) verify buying an existing symbol is blocked with specific error message, (2) verify selling an existing position is still allowed. These tests prevent regression if someone refactors the gate logic.

Tests Added:

- `test_position_stacking_blocked` - verifies buying existing symbol is blocked
- `test_sell_existing_position_allowed` - verifies selling is still allowed

---

## What are the key lessons from position stacking bugs?

> Four lessons: (1) count contracts, not just symbols - a single symbol can hide unlimited risk, (2) prevention beats detection - by the time detection fires, bad trades already exist, (3) test edge cases - the gate passed all tests but had this fatal flaw, (4) two-layer defense - always have monitoring as backup.

1. **Count contracts, not just symbols** - A single symbol can hide unlimited risk
2. **Prevention > Detection** - By the time detection fires, trades are already made
3. **Test edge cases** - The gate passed all tests but had this fatal flaw
4. **Two-layer defense** - Always have a backup monitoring system

---

## How does this lesson integrate with the RLHF system?

> This lesson (LL-275) is embedded in LanceDB with semantic search enabled. Before any trade, the system queries "position stacking" or "contract accumulation" and retrieves this lesson, reminding the decision engine about the fix and ensuring the pattern isn't repeated.

The Thompson Sampling model now weights iron condor strategies lower until the position stacking fix has been validated over 30+ trades. The RLHF feedback loop recorded this as a critical failure pattern.

---

## Status

- **Fix deployed**: PR #2702 merged (SHA: bf253af)
- **Tests**: 878 passed
- **CI**: Passing
- **Position**: Still blocked by PDT until tomorrow
- **Lesson**: Recorded in LanceDB and lessons-learned.md

---

_This lesson cost $1,472 in paper trading. The real value is ensuring it never happens with real money._

---

Evidence: https://github.com/IgorGanapolsky/trading

---

*Related: [Complete Guide to AI Iron Condor Trading](/trading/2026/01/21/iron-condors-ai-trading-complete-guide/) | [Feedback-Driven Context Pipelines](/trading/2026/02/15/feedback-driven-context-pipelines-2026/)*
