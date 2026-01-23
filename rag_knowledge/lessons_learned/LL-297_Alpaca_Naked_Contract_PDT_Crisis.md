# LL-297: Alpaca Naked Contract & PDT Crisis - Root Cause Analysis

**Date**: January 23, 2026
**Category**: Trading / Risk Management / CRITICAL BUG
**Severity**: CRITICAL
**Source**: Alpaca Support Email (Braxton, Jan 22, 2026)

## Executive Summary

On Jan 21-22, 2026, trading was completely blocked due to TWO issues:
1. **Naked Contract Risk** - Attempting to close longs would leave shorts uncovered
2. **PDT Protection** - Day trade limit reached

This lesson documents the root cause and prevention measures.

## The Crisis

### Position State (Before Crisis)
```
SPY260220P00653000:
  - Short: 2 contracts (sold puts)
  - Long: 8 contracts (bought puts for protection)
```

### What Went Wrong
When CTO attempted to close the 8 long contracts:
- This would leave 2 short contracts UNCOVERED
- Uncovered short options = **NAKED POSITIONS**
- **Alpaca does NOT allow naked contracts** → ALL TRADES BLOCKED

## Root Cause: Spread Leg Imbalance

The position had mismatched legs:
- 8 long puts (protection)
- 2 short puts (premium collection)

**This is NOT a proper spread.** A proper spread has equal legs (e.g., 2 long + 2 short).

### How This Happened
1. Accumulated long puts over multiple trades
2. Short puts were not increased proportionally
3. When trying to close, longs exceeded shorts
4. Closing longs first would create naked shorts

## Prevention Rules (MANDATORY)

### Rule 1: ALWAYS Close Spreads as Multi-Leg Orders
```python
# WRONG - Creates naked risk
alpaca.close_position(long_leg)  # ❌ NEVER DO THIS
alpaca.close_position(short_leg)  # Now naked!

# RIGHT - Close as spread
alpaca.submit_order(
    symbol="SPY",
    qty=2,
    side="buy",
    type="market",
    order_class="bracket",
    legs=[close_short, close_long]  # ✅ Both legs together
)
```

### Rule 2: Maintain Equal Spread Legs
```
VALID IRON CONDOR:
  - 1 short put, 1 long put (bull put spread)
  - 1 short call, 1 long call (bear call spread)

INVALID (causes naked risk):
  - 2 short puts, 8 long puts  ❌
  - 1 short call, 3 long calls ❌
```

### Rule 3: Close Shorts BEFORE Longs (If Not Multi-Leg)
If multi-leg not possible:
1. Close short positions FIRST
2. THEN close long positions
3. NEVER close longs while shorts remain open

### Rule 4: Pre-Close Validation Check
Before ANY close order:
```python
def validate_close_order(position, close_qty):
    short_qty = position.short_contracts
    long_qty = position.long_contracts

    # If closing longs, ensure shorts are closed first or equal
    if closing_longs:
        remaining_longs = long_qty - close_qty
        if remaining_longs < short_qty:
            raise NakedRiskError("Would create naked shorts!")

    return True
```

## PDT Rules (Secondary Issue)

### What Is a Day Trade?
- Opening buy → closing sell SAME DAY
- Opening sell → closing buy SAME DAY
- **Expiring same-day options also count!**

### PDT Limits
| Account Equity | Day Trade Limit |
|----------------|-----------------|
| < $25,000 | 3 per rolling 5 days |
| >= $25,000 | **UNLIMITED** |

### Day Trade "Drop Off"
- Trades expire from count after 5 business days
- Monday trade → drops off following Monday

## Why $30K Account Solves PDT (But NOT Naked Risk)

✅ **$30K > $25K** = No PDT restrictions, can day trade freely
❌ **Naked risk is ALWAYS blocked** regardless of account size

**The naked contract issue would have happened even with a $1M account.**

## Implementation Checklist

### Code Changes Required
- [ ] Add `validate_spread_balance()` before any close order
- [ ] Implement multi-leg close orders for all spreads
- [ ] Add pre-trade check: `will_this_create_naked_position()?`
- [ ] Alert if spread legs become imbalanced

### Trading Rules (MANDATORY)
- [ ] NEVER accumulate more long contracts than short contracts
- [ ] ALWAYS close spreads as multi-leg orders
- [ ] If single-leg close required: shorts FIRST, longs SECOND
- [ ] Review position balance daily

## Code Implementation

```python
# src/utils/spread_safety.py

def check_naked_risk(positions: list, proposed_close: dict) -> bool:
    """
    Check if closing a position would create naked risk.

    Returns True if safe, raises NakedRiskError if dangerous.
    """
    symbol = proposed_close['symbol']
    close_qty = proposed_close['qty']
    close_side = proposed_close['side']  # 'long' or 'short'

    # Find matching positions
    for pos in positions:
        if pos.symbol == symbol:
            if close_side == 'long':
                remaining_longs = pos.long_qty - close_qty
                if remaining_longs < pos.short_qty:
                    raise NakedRiskError(
                        f"Closing {close_qty} longs would leave "
                        f"{pos.short_qty} shorts uncovered!"
                    )
    return True

def close_spread_safely(client, spread_positions):
    """
    Close a spread using multi-leg order to avoid naked risk.
    """
    # Build multi-leg close order
    legs = []
    for pos in spread_positions:
        if pos.qty > 0:  # Long position
            legs.append({"symbol": pos.symbol, "side": "sell", "qty": pos.qty})
        else:  # Short position
            legs.append({"symbol": pos.symbol, "side": "buy", "qty": abs(pos.qty)})

    # Submit as single multi-leg order
    return client.submit_multileg_order(legs)
```

## Tags

`naked-risk`, `PDT`, `spread-safety`, `crisis`, `alpaca`, `critical`

## Source

Alpaca Support Email from Braxton, January 22, 2026, 5:02 PM EST
