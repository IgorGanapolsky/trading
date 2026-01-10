---
layout: post
title: "LL-124: Phil Town CSP Strategy Not Executing Trades"
date: 2026-01-09
---

# LL-124: Phil Town CSP Strategy Not Executing Trades

## Incident Date
January 9, 2026

## Severity
**CRITICAL** - Paper account sat idle for 4 days with $5,000, 0 trades

## Summary
The Phil Town Cash-Secured Put (CSP) strategy was NOT executing trades due to two bugs:
1. **Wrong condition in rule_one_trader.py**: Only traded when stock was BELOW MOS (defeats the purpose!)
2. **Misleading counters in orchestrator**: `puts_executed` counter incremented on logging, not execution

## Root Cause Analysis

### Bug 1: Inverted Trade Logic
The code in `scripts/rule_one_trader.py` lines 310-320 had:
```python
if "STRONG BUY" in recommendation and "Below MOS" in recommendation:
    # Only traded here
```

**Problem**: Phil Town's strategy is to SELL PUTS when stock is ABOVE MOS to "get paid to wait" for your price. The code only traded when stock was already below MOS - which defeats the entire purpose!

**Correct Logic**:
- Stock BELOW MOS → Buy shares directly (it's on sale!)
- Stock ABOVE MOS but BELOW Sticker → SELL PUT at MOS (getting paid to wait) ← THIS IS THE STRATEGY
- Stock ABOVE Sticker → Don't trade (overvalued)

### Bug 2: Dishonest Counters
The orchestrator's `run_options_strategy()` had:
```python
results["puts_executed"] += 1  # MISLEADING!
```
This counter incremented when LOGGING signals, not when executing orders. It made the system appear to be trading when it wasn't.

## Evidence
- Paper account: $5,000 equity, 0 positions, 0 orders for 4+ days
- Alpaca dashboard showed: "No orders. Place a trade..."
- Workflow logs showed "puts_executed: 3" but no actual orders in Alpaca

## Fixes Applied

### Fix 1: Corrected Trade Logic (rule_one_trader.py)
```python
# NOW TRADES WHEN:
elif "BUY" in recommendation:
    # Stock is above MOS but below Sticker = "getting paid to wait"
    logger.info(f"  🎯 ACTIONABLE: {symbol} above MOS, below Sticker - Selling CSP!")
    trade = execute_phil_town_csp(client, symbol, analysis)
```

### Fix 2: Honest Counters (orchestrator/main.py)
```python
results["puts_logged"] = 0      # HONEST: we log, not execute here
results["calls_logged"] = 0     # HONEST: we log, not execute here
results["note"] = "Signals logged here; execution in rule_one_trader.py"
```

## Verification
After fix:
- Stocks trading between MOS and Sticker will trigger CSP orders
- Counters accurately reflect what the code does
- Actual execution happens in `rule_one_trader.py` which submits real orders

## Prevention
1. **Counter naming**: Use `_logged` or `_analyzed` for non-execution counters
2. **End-to-end testing**: Verify orders appear in Alpaca, not just logs
3. **Daily trade activity monitor**: Alert when $5K account has 0 trades for 3+ days

## Related Files
- `scripts/rule_one_trader.py` - Fixed trade condition
- `src/orchestrator/main.py` - Fixed misleading counters
- `.github/workflows/daily-trading.yml` - Calls rule_one_trader.py

## Phil Town Strategy Reminder
From "Payback Time" by Phil Town:
> "We sell puts on wonderful companies at their Margin of Safety price. If the stock drops to our price, we get to buy it at a huge discount. If it doesn't, we keep the premium. Either way, we win."

The key insight: You sell puts ABOVE your target price to GET PAID WHILE WAITING.

## Tags
- phil-town
- options
- csp
- execution-failure
- paper-trading
- critical-bug
