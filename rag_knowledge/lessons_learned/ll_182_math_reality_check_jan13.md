---
id: ll_182
title: Critical Math Reality Check - Credit Spread Risk/Reward
severity: CRITICAL
date: 2026-01-13
category: strategy_math
tags: [math, credit-spreads, risk-reward, north-star, win-rate]
---

## Critical Finding

**Credit spreads have a 4:1 risk/reward ratio that requires 80%+ win rate to break even.**

## The Math

### Raw Risk/Reward (Hold to Expiration)
- Premium collected: $100
- Max loss (collateral): $500
- Risk: $400 to make $100
- Break-even win rate: **80%**

### With Take Profit (50%) & Stop Loss (100%)
- Take profit: +$50
- Stop loss: -$100
- Risk/Reward: 2:1
- Break-even win rate: **67%**

### Expected Value by Win Rate (10 spreads)
| Win Rate | EV/Spread | Daily (10 spreads) |
|----------|-----------|-------------------|
| 50% | -$25 | -$50/day |
| 60% | -$10 | -$20/day |
| 70% | +$5 | +$10/day |
| 80% | +$20 | +$40/day |

## North Star Reality

**$100/day REQUIRES:**
- $12,500+ capital (not $5,000)
- 80%+ win rate sustained
- 25 spreads/week (not 10)

**With current $5K:**
- Max realistic daily income: ~$40/day (at 80% win rate)
- This is NOT $100/day

## Timeline to North Star

| Month | Capital | Potential Daily |
|-------|---------|-----------------|
| Now | $5,000 | $40/day max |
| 6 | $8,500 | $68/day max |
| 11 | $13,300 | $100/day possible |

## Action Items

1. **Recalibrate expectations**: $40/day is realistic target now
2. **Track win rate obsessively**: Need 80%+ to be profitable
3. **Do NOT increase position size** until win rate proven
4. **Compound slowly**: 11 months to $100/day is honest

## CEO Acknowledgment Required

The math does not support $100/day with $5K capital.
We can reach $100/day, but it requires:
- 11+ months of disciplined trading
- 80%+ win rate
- Continuous deposits
- Zero major losses (Rule #1)

## Tags
critical, math, credit-spreads, risk-reward, north-star, reality-check
