# LL-303: Iron Condor Execution Best Practices - Timing and Orders

**Date**: January 25, 2026
**Category**: Execution, Trading Operations
**Severity**: MEDIUM (affects fill quality and slippage)
**Status**: Research Complete

## Executive Summary

Optimal iron condor execution requires careful timing (avoid market open/close), proper order types (limit orders, complex orders), and patience for good fills.

## Best Entry Times

| Time Window | Quality | Notes |
|-------------|---------|-------|
| 9:30-10:00 AM | ❌ Avoid | High volatility, wide spreads |
| 10:00-11:00 AM | ⚠️ Acceptable | Spreads tightening |
| 11:00 AM-2:00 PM | ✅ **Optimal** | "Midday lull", tightest spreads |
| 2:00-3:30 PM | ⚠️ Acceptable | Can work, watch for news |
| 3:30-4:00 PM | ❌ Avoid | Gamma risk, late-day whipsaws |

**Key Insight:** The "midday lull" (11 AM - 2 PM ET) typically offers the tightest bid-ask spreads and most stable pricing.

## Order Execution Rules

### 1. Always Use Complex Orders
Enter all 4 legs simultaneously as a single order:
```
BUY 1 SPY 570P (long put - protection)
SELL 1 SPY 580P (short put - premium)
SELL 1 SPY 620C (short call - premium)
BUY 1 SPY 625C (long call - protection)
Net Credit: $2.50 (example)
```

**Why:** Legging in separately = slippage + chasing the market + poor fills

### 2. Use Limit Orders Only
- **Never use market orders** on options
- Start at the midpoint between bid and ask
- Walk price up in $0.01-$0.05 increments if not filled
- Skip the trade if can't get reasonable fill

### 3. Patience Over Speed
- Don't chase fills
- If spread is wide, wait for better pricing
- A $0.10 better fill × 4 legs = $40 savings per contract

## SPY Liquidity Advantage

SPY is the most liquid ETF for iron condors:
- Tightest bid-ask spreads
- Deepest order book
- No earnings surprises (unlike individual stocks)
- Penny-wide quotes at popular strikes

**Comparison:**
| Underlying | Typical Spread | Fill Quality |
|------------|----------------|--------------|
| SPY | $0.01-0.03 | Excellent |
| IWM | $0.02-0.05 | Good |
| QQQ | $0.01-0.04 | Very Good |
| Individual stocks | $0.05-0.20+ | Variable |

## Exit Timing

### Profit Exits (50% of max)
- Can execute any time during trading day
- Midday usually offers best fills
- No rush - use limit orders

### Stop-Loss Exits (200% of credit)
- Execute immediately when triggered
- Don't wait for "better" prices
- Use limit but be willing to pay up slightly

### Time-Based Exits (7 DTE)
- Close before final week begins
- Monday/Tuesday of expiration week ideal
- Avoids gamma acceleration

## Execution Checklist

Before placing iron condor order:
- [ ] Time between 10:00 AM - 3:00 PM ET?
- [ ] Complex order (all 4 legs together)?
- [ ] Limit order at midpoint or better?
- [ ] Spread width reasonable (<$0.05 per leg)?
- [ ] No major news in next 2 hours?

## Common Execution Mistakes

1. **Legging in** - Entering spreads separately
2. **Market orders** - Giving up edge to market makers
3. **Impatience** - Chasing fills, paying wide spreads
4. **Opening at market open** - Worst fills of the day
5. **Holding into close** - Gamma risk in final 30 minutes

## Alpaca-Specific Notes

From our experience (LL-168, LL-291):
- Alpaca does NOT support trailing stops on options
- Use bracket orders when available
- Complex orders may fill as separate legs
- Monitor fill prices carefully

## Sources

- [Option Alpha - Iron Condor Strategy](https://optionalpha.com/strategies/iron-condor)
- [TradeStation - Iron Condor Guide](https://www.tradestation.com/insights/2025/10/28/iron-condor-strategy-for-trading-neutral-markets-tradestation/)
- [CBOE - Zero-Day SPX Iron Condor](https://www.cboe.com/insights/posts/henry-schwartzs-zero-day-spx-iron-condor-strategy-a-deep-dive/)
- [The Option Premium - Iron Condor Mastery](https://www.theoptionpremium.com/p/mastering-the-iron-condor-a-step-by-step-comprehensive-guide-to-a-defined-risk-options-strategy)

## Tags
execution, timing, orders, liquidity, slippage, iron_condor, best_practices

---

*Researched January 25, 2026. Optimal entry: 11 AM - 2 PM ET with limit orders.*
