---
layout: post
title: "Day 74: Emergency Fix - Why We Switched from SPY to SOFI"
date: 2026-01-13
categories: [lessons, trading]
tags: [options, csp, sofi, spy, collateral]
description: "Our AI tried to trade SPY with a $5K account. Here's what went wrong and how we fixed it."
---

# Day 74: The SPY Mistake

At 9:35 AM today, our trading system tried to sell a cash-secured put on SPY.

It failed. Here's why, and what we learned.

## The Error

```
ERROR: Insufficient buying power
Required collateral: $58,000
Available: $5,000
Trade: SPY $580 PUT
```

Wait, what? SPY? With a $5K account?

## Root Cause Analysis

Our system was still configured for the old $100K account. The watchlist included SPY because... well, because it worked before.

But with $5K:
- SPY $580 strike requires $58,000 collateral
- That's **11.6x our entire account**
- The trade was mathematically impossible

## The Fix

We updated the configuration immediately:

**Before:**
```python
WATCHLIST = ["SPY", "AAPL", "MSFT", "SOFI", "F"]
```

**After:**
```python
WATCHLIST = ["SOFI", "F", "PLTR", "AMD"]  # All under $25
MAX_COLLATERAL_PCT = 0.20  # Max 20% per trade
```

## Why SOFI?

SOFI at $5 strike requires only $500 collateral:
- Fits within 20% position limit ($1,000)
- Premium is ~$0.10-0.20 per contract
- ROI: 2-4% per month
- Company has solid fundamentals

## The Lesson Recorded

This became **LL-148** in our RAG system:

> **Lesson**: Always verify collateral requirements against account size before adding stocks to watchlist. SPY requires $50K+ collateral per contract.

> **Prevention**: Add pre-trade collateral check that rejects any trade requiring more than MAX_COLLATERAL_PCT of available capital.

## Code Changes

We added a hard block in the trade gateway:

```python
def validate_collateral(self, trade):
    required = trade.strike * 100  # CSP collateral
    available = self.get_buying_power()
    max_allowed = available * MAX_COLLATERAL_PCT

    if required > max_allowed:
        raise InsufficientCollateralError(
            f"Trade requires ${required}, max allowed ${max_allowed}"
        )
```

## What the AI Learned

Claude (our CTO) now knows:
1. Check collateral BEFORE suggesting trades
2. Filter watchlist by account size
3. Small accounts need small stocks

This is why we record every lesson. The AI literally cannot make this mistake again.

## Today's Actual Trade

After the fix:
- **Symbol**: SOFI
- **Strike**: $5
- **Expiry**: Jan 17, 2026
- **Premium**: $0.12
- **Collateral**: $500
- **Status**: Order placed successfully

---

*Day 74 of 90. Learning from every mistake. [See all 16 lessons](/trading/lessons/)*
