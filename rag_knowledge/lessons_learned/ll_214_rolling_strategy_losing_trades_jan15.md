# LL-214: Rolling Strategy for Losing Credit Spread Trades

**ID**: LL-214
**Date**: January 15, 2026
**Category**: Strategy / Risk Management
**Severity**: MEDIUM
**Source**: YouTube Research - "Invest with Henry" video on credit spreads

## Context

When a credit spread trade goes against us (stock drops toward or below sold strike), we have options beyond just taking the loss.

## Rolling Strategy: "Down and Out"

### When to Consider Rolling
- Stock is trending toward your short strike
- You believe the underlying will recover (fundamentals intact)
- Days to expiration are low (can gain more time)
- NOT when fundamentals have changed or stock is in freefall

### How to Roll Down and Out
1. **Close** the existing spread (buy back the sold put, sell the bought put)
2. **Open** a new spread simultaneously:
   - **Lower strike prices** (further OTM)
   - **Further expiration** (30-45 more days)
3. Ideally, collect small net credit or break-even on the roll

### Example
```
Original: Sold $580 put, bought $575 put, 14 DTE
Stock drops to $582 (getting close)
Roll to: Sell $575 put, buy $570 put, 45 DTE
Result: Extended time, lower strikes, small credit received
```

### When NOT to Roll
- Stock has broken through support with high volume
- Fundamental thesis is broken
- Would require rolling for a net debit (throwing good money after bad)
- Already rolled once — cut losses, don't compound

## Assignment Risk Warning

If stock is BETWEEN your two strike prices on expiration day:
- **HIGH RISK** of assignment (forced to buy 100 shares)
- **MUST close position manually** before market close
- Do not let spreads expire when pinned between strikes

## Integration with Our Strategy

| Our Rule | Rolling Consideration |
|----------|----------------------|
| 2x credit stop-loss | Roll BEFORE hitting 2x loss if thesis intact |
| 50% profit exit | Take profits early; don't give back gains |
| SPY/IWM only | These have high liquidity for efficient rolls |

## Prevention (How to Avoid Needing to Roll)
1. Use 30-delta (not ATM) for margin of safety
2. Exit at 50% profit — don't hold to expiration
3. Honor stop-loss (2x credit) — don't hope and pray
4. Size positions at 5% max — one loss won't break you

## Key Takeaway

Rolling is a **tool, not a crutch**. Use it when fundamentals support recovery. Don't use it to avoid admitting you were wrong.
