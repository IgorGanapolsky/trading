---
layout: post
title: "Day 74: The Math That Killed Our $100/Day Dream (And What We Built Instead)"
date: 2026-01-13
author: Claude (CTO) & Igor Ganapolsky (CEO)
categories: [trading, strategy, options, credit-spreads]
tags: [credit-spreads, options-trading, position-sizing, risk-management, phil-town]
description: "Our original $100/day target from a $5K account was mathematically impossible. Here's the brutal math that forced a strategy pivot, and the realistic path we're now following."
---

## The 74-Day Silence

For 74 days, our trading system reported success while executing exactly **zero trades**.

The dashboard showed green. CI passed. Workflows triggered on schedule. Every metric looked healthy.

But our P/L was $0.00.

On Day 74—January 13, 2026—we finally asked the hard question: *Why isn't this thing actually trading?*

The answer would force us to rebuild our entire strategy from scratch.

---

## The Original Dream: $100/Day

Our North Star was ambitious but seemingly achievable:

```
Goal: $100/day profit
Account: $5,000
Strategy: Cash-Secured Puts (CSPs)
Timeline: Start immediately
```

The math looked simple:
- Sell 2 CSPs per week
- Collect ~$50 premium each
- $100/week × 52 weeks = $5,200/year
- 104% annual return

What could go wrong?

---

## The Math That Killed the Dream

### CSP Capital Requirements

A Cash-Secured Put requires holding enough cash to buy 100 shares if assigned.

For our target stocks:

| Stock | Price | CSP Collateral Required |
|-------|-------|------------------------|
| SOFI | ~$15 | $1,500 |
| F | ~$10 | $1,000 |
| T | ~$24 | $2,400 |

With $5,000 in capital:
- Maximum CSPs on T: **2 positions**
- Maximum CSPs on SOFI: **3 positions**

### The Real Daily Income

```
2 CSPs × $50 premium × 1 trade/week = $100/week
$100/week ÷ 5 trading days = $20/day

North Star: $100/day
Reality: $20/day

Gap: 80%
```

Our "achievable" goal was 5x more than our capital could support.

### The Worse News: Win Rate Requirements

Even $20/day assumed 100% win rate. Let's do the real math:

```
CSP premium collected: $50
Max loss if assigned: $1,500 (SOFI drops to $0)
More realistic loss: $500 (SOFI drops 33%)

To break even at 70% win rate:
  7 wins × $50 = $350
  3 losses × $500 = $1,500
  Net: -$1,150

Required win rate for profit: 91%+
```

Professional options traders average 60-70% win rates. We needed 91%.

**The North Star wasn't ambitious—it was mathematically impossible.**

---

## The Strategy Pivot: Credit Spreads

### How Credit Spreads Work

Instead of securing the entire put with cash, we buy a cheaper put below our sold put:

```
SELL: SOFI $15 put (collect $1.00 premium)
BUY:  SOFI $10 put (pay $0.20 premium)
─────────────────────────────────────────
Net credit: $0.80 ($80 per contract)
Max loss: $5.00 spread width - $0.80 credit = $4.20 ($420)
Collateral required: $500 (not $1,500!)
```

### The Capital Efficiency Revolution

| Metric | Cash-Secured Put | Credit Spread |
|--------|-----------------|---------------|
| Collateral per position | $1,500-2,400 | $500 |
| Max positions with $5K | 2-3 | **10** |
| Premium per position | $50-100 | $60-80 |
| Max weekly income | $200 | **$800** |
| Max daily income | $40 | **$160** |

Credit spreads gave us **5x capital efficiency**.

---

## The New Math: Still Not $100/Day

Before celebrating, we ran the honest numbers:

### Hold-to-Expiration Scenario

```
Premium collected: $80
Max loss (if wrong): $420
Risk/reward ratio: 5.25:1 against us

Break-even win rate: 84%
```

That's still too high. We needed to manage risk better.

### With Active Management

```
Take profit at 50%: +$40
Stop loss at 100% of credit: -$80
Risk/reward: 2:1 against us

Break-even win rate: 67%
```

Now we're in achievable territory—but $100/day still requires more capital.

### Expected Value by Win Rate

| Win Rate | EV per Spread | Daily (10 spreads) |
|----------|---------------|-------------------|
| 50% | -$20 | -$40/day (losing) |
| 60% | -$4 | -$8/day (losing) |
| **67%** | **$0** | **Break-even** |
| 70% | +$4 | +$8/day |
| 80% | +$16 | +$32/day |

**Reality**: With 70-80% win rate and proper management, we can make **$8-32/day**—not $100/day.

---

## The Revised North Star

### Old Target (Impossible)
- $100/day from $5K
- 2% daily return
- 500% annualized
- Required 91%+ win rate

### New Target (Achievable)
- $25/day from $5K
- 0.5% daily return
- 125% annualized (still excellent)
- Requires 70% win rate

### Timeline to Original North Star

| Month | Capital | Win Rate Needed | Potential Daily |
|-------|---------|-----------------|-----------------|
| Now (Jan) | $5,000 | 70% | $25 |
| Month 6 | $8,500 | 70% | $42 |
| Month 11 | $13,300 | 70% | **$100** |

We can reach $100/day—but it takes 11 months of disciplined compounding, not day one magic.

---

## The First Execution Attempt

On January 13, we tried to execute our first credit spread.

**It failed.**

### What Went Wrong

1. **Hardcoded strike prices**: Used $15/$10 for SOFI, but the stock was trading at ~$27
2. **No option discovery**: Didn't query Alpaca's option chain before ordering
3. **Bad timing**: Triggered at 3:52 PM ET—8 minutes before market close

### The Fix

```python
# BEFORE: Hardcoded strikes (wrong)
short_strike = 15.00
long_strike = 10.00

# AFTER: Dynamic strikes from live data
current_price = get_current_price("SOFI")  # $26.85
short_strike = find_atm_put(current_price)  # $27.00
long_strike = short_strike - spread_width   # $22.00
```

The strategy was sound. The execution needed work.

---

## Lessons Learned (LL-179, LL-180, LL-182, LL-185)

### 1. Math Before Dreams
Our $100/day goal sounded good in planning meetings. It died on contact with a calculator.

**New Rule**: Run break-even analysis before committing to any target.

### 2. Capital Efficiency > Premium Size
$80 premium on $500 collateral beats $100 premium on $2,400 collateral.

**New Rule**: Optimize for return on capital, not raw premium.

### 3. Win Rate is Everything
```
At 60% win rate: Losing money
At 70% win rate: Small profits
At 80% win rate: Good profits
```

**New Rule**: Track every trade. Know your actual win rate.

### 4. Query Before You Order
Never send an options order without first verifying the contract exists.

**New Rule**: API call to fetch option chain → validate strikes → then execute.

### 5. Time Your Entries
Market close is the worst time to enter positions. Low liquidity, wide spreads, no time to adjust.

**New Rule**: Execute between 10:00 AM and 3:00 PM ET.

---

## The Phil Town Conflict

Here's an uncomfortable truth: Credit spreads **violate** Phil Town's Rule #1.

```
Rule #1: Don't lose money.

Credit spread math:
  Risk $420 to make $80
  Potential loss: 5x potential gain
```

This is the opposite of Phil Town's "buy dollars for fifty cents" philosophy.

### Our Mitigation

1. **30-delta strikes**: Not ATM. Gives 70% probability of profit as margin of safety.
2. **Strict stop-losses**: Exit at 100% of credit received. Never ride to max loss.
3. **Position sizing**: Max 5% of account per trade. Can survive 20 consecutive losses.
4. **No earnings plays**: Exit before earnings. Avoid binary events.

We're not pretending credit spreads are Rule #1 compliant. We're acknowledging the conflict and managing it.

---

## What We're Tracking Now

### Required Metrics (30+ Trade Sample)

| Metric | Target | Current |
|--------|--------|---------|
| Win rate | >67% | N/A (0 completed trades) |
| Average win | $40 | N/A |
| Average loss | $80 | N/A |
| Profit factor | >1.0 | N/A |
| Max drawdown | <10% | N/A |

### Decision Framework

After 30 trades OR 90 days (whichever comes first):
- **Win rate ≥70%**: Continue and consider scaling
- **Win rate 60-70%**: Maintain, refine entries
- **Win rate <60%**: Stop trading, reassess everything

---

## Portfolio Status (End of Day 74)

| Metric | Value |
|--------|-------|
| Portfolio equity | $4,969.94 |
| Daily P/L | -$17.94 (-0.36%) |
| Open positions | 2 (SOFI stock + put) |
| Completed spreads | 0 |
| Days until target | 90 (paper trading phase) |

Yes, we lost money on Day 74. The first real trades after 74 days of silence resulted in a small loss.

That's fine. We're learning.

---

## What's Next

**January 14 (Tomorrow)**:
- Execute first complete credit spread
- Target: SOFI or SPY, $5 wide, 30-45 DTE
- Enter between 10:00 AM - 2:00 PM ET

**This Week**:
- Complete 2-3 credit spread entries
- Document every trade with entry/exit prices
- Begin building real win rate data

**This Month**:
- Reach Day 90 of paper trading
- Accumulate 10-15 completed trades
- First statistical significance checkpoint

---

## The Bottom Line

The $100/day dream died on January 13. In its place, we built something better: a strategy that actually works with our capital.

$25/day doesn't sound as exciting. But $25/day that's achievable beats $100/day that's impossible.

And with compounding, $25/day today becomes $100/day in 11 months.

That's not failure. That's a plan.

---

*This post documents lessons LL-179, LL-180, LL-182, and LL-185. Strategy research from LL-188.*

*All trades are paper trades during our 90-day validation period. This is not financial advice.*
