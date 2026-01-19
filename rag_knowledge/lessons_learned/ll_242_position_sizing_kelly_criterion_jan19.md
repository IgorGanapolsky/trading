# LL-242: Position Sizing & Kelly Criterion for Small Options Accounts

**Date**: 2026-01-19
**Category**: Risk Management, Position Sizing, Math
**Severity**: HIGH
**Tags**: `position-sizing`, `kelly-criterion`, `risk-management`, `small-account`
**Source**: Weekend research - Kelly criterion applications in options trading

## Summary

Position sizing is **the single most important risk management decision**. This lesson documents the Kelly Criterion and practical modifications for small options accounts.

## The Kelly Criterion

### Formula
```
Kelly % = W - [(1-W) / R]
```

Where:
- **W** = Win rate (probability of winning)
- **R** = Win/Loss ratio (average win / average loss)

### Example: Our Credit Spread Strategy
- Win rate (W): 80% = 0.80
- Risk/Reward: Risk $210 to make $90 → R = 90/210 = 0.43

```
Kelly % = 0.80 - [(1-0.80) / 0.43]
Kelly % = 0.80 - [0.20 / 0.43]
Kelly % = 0.80 - 0.465
Kelly % = 0.335 (33.5%)
```

**Full Kelly suggests 33.5% per trade** - but this is too aggressive!

## Why Full Kelly is Dangerous

| Strategy | Max Drawdown | Stress Level | Recovery Time |
|----------|--------------|--------------|---------------|
| Full Kelly (33%) | 50-70% | Extreme | Months |
| Half Kelly (17%) | 25-35% | High | Weeks |
| Quarter Kelly (8%) | 10-20% | Moderate | Days |
| 5% Fixed | 5-10% | Low | Minimal |

### The Problem with Full Kelly
- Assumes **perfect** knowledge of probabilities
- One bad streak can devastate account
- Most traders can't stomach 50%+ drawdowns
- Real win rates vary; estimates have errors

## Practical Position Sizing for $5K Account

### Our CLAUDE.md Rule: 5% Max Risk
```
$4,959.26 x 5% = $247.95 max risk per trade
```

This is approximately **Quarter Kelly** (8% would be $397), which is appropriate because:
1. Our win rate estimate has uncertainty
2. We're in paper trading validation phase
3. Small accounts can't afford large drawdowns
4. Consistent small gains compound better than volatile swings

### Position Size Calculation
With $3-wide spreads and $90 credit:
- Max loss = $300 - $90 = $210
- Max loss with stop at 2x: $90 (original credit)
- Risk per trade: $90-$210 depending on management

**Result**: We can trade 1-2 spreads at a time max.

## The 2% Rule (Traditional Alternative)

Many traders use a simpler rule:
```
Risk per trade = Account x 2% = $4,959 x 2% = $99
```

This is **more conservative** than Kelly and appropriate for:
- Newer traders
- Accounts under $10K
- Strategies with uncertain win rates

## Key Insights

### 1. Small Accounts Need Extra Conservatism
- Single bad trade = significant % loss
- Recovery math is brutal: 50% loss needs 100% gain to recover
- Build capital slowly through consistency

### 2. Fractional Kelly is Optimal
Quarter to Half Kelly provides:
- 75% of Full Kelly returns
- 50% of Full Kelly variance
- Much better risk-adjusted returns

### 3. Our Strategy Alignment
| Metric | CLAUDE.md | Kelly Optimal | Status |
|--------|-----------|---------------|--------|
| Max position | 5% ($248) | Quarter Kelly (~8%) | ✅ Conservative |
| Positions at once | 1 | 1-2 | ✅ Appropriate |
| Stop loss | 2x credit | Mandatory | ✅ Risk controlled |

## Action Items

1. **Never exceed 5% risk** - this is hard-coded
2. **Start with 1 position** - scale only after proven win rate
3. **Track actual win rate** - adjust Kelly calculation quarterly
4. **Log position sizes** - ensure consistency

## Mathematical Reality Check

To reach $100/day with 5% position sizing:
- Need ~$50K account (2% daily on 5% risk is aggressive)
- Current path: compound gains + deposits over 2.5-3 years
- This is **realistic** per LL-185 and recovery path in CLAUDE.md

## Sources

- [Kelly Criterion Calculator](https://www.backtestbase.com/education/how-much-risk-per-trade)
- [Position Sizing Strategies](https://www.quantifiedstrategies.com/position-sizing-strategies/)
- [Kelly Criterion for Options](https://www.environmentaltradingedge.com/trading-education/how-to-use-kelly-criterion-trading-options)
- [Alpha Theory - Kelly in Practice](https://www.alphatheory.com/blog/kelly-criterion-in-practice-1)

## Prevention/Future Learning

- Always calculate Kelly before trading a new strategy
- Use conservative (quarter Kelly) until win rate is proven
- Never risk more than you can afford to lose
- Position sizing > entry timing for long-term success
