---
layout: post
title: "$5K to $100K: Journey to $6K/Month via Options"
date: 2026-02-01
last_modified_at: "2026-02-01"
author: Igor Ganapolsky
categories: [trading, personal-finance, options, journey]
tags:
  [
    iron-condors,
    SPY,
    passive-income,
    financial-independence,
    options-trading,
    lessons-learned,
  ]
description: "Building an AI trading system: 74 days of silence, a painful SOFI loss, and the pivot to iron condors that finally made the math work."
image: "/assets/snapshots/progress_latest.png"

---

# From $5K to $100K: My Journey to $6,000/Month Passive Income


## Answer Block

> **Answer Block:** I was born in Kiev, Ukraine, on November 14th, 1979. By the time I turn 50 - November 14th, 2029 - I want to achieve something that felt impossible for most of

_February 1, 2026_

I was born in Kiev, Ukraine, on November 14th, 1979. By the time I turn 50 - November 14th, 2029 - I want to achieve something that felt impossible for most of my life: **financial independence**.

Not "rich." Not "wealthy." Just free. Free to work on what matters. Free from the anxiety of whether next month's bills are covered. The number I calculated: **$6,000 per month after taxes**. That's my North Star.

This is the story of how I'm getting there.

---

## The Dream That Started With $5,000

In late 2025, I started building an AI-powered options trading system with a bold target: **$100 per day** from a $5,000 paper trading account.

The math seemed simple enough:

- Sell 2 options contracts per week
- Collect $50 premium each
- Profit: $100/week = $5,200/year
- Return: 104% annually

I built the system with Claude AI as my "CTO" - an AI that could execute trades, manage risk, and learn from every decision. We created 23 automated workflows, 5 risk gates, sentiment analysis, multi-factor scoring... the works.

**Then I waited.**

---

## The Silent 74 Days

From November 1, 2025 through January 12, 2026, my trading system executed exactly **zero trades**.

Not one.

The dashboard showed green. All tests passed. Workflows triggered on schedule. Every metric looked healthy.

But my P/L was $0.00.

For 74 days, I had built an elaborate system that did absolutely nothing.

### What Went Wrong

When I finally audited the code, I found the bugs that had been silently killing every trade:

**Bug #1: Timezone Confusion**

```python
def is_market_open():
    now = datetime.utcnow()  # Checking UTC, not Eastern Time
    return 9 <= now.hour < 16
```

When it was 9:35 AM in New York, the code thought it was 2:35 PM. Market "closed."

**Bug #2: Hardcoded Price**

```python
def should_open_position(symbol):
    price = 600.00  # Hardcoded SPY price!
    required_capital = price * 100  # $60,000 needed
```

My config said trade SOFI at $15/share. The code checked if I could afford SPY at $600/share. Required capital: $60,000. My account: $5,000. Every trade blocked.

**Bug #3: Error Swallowing**

```yaml
steps:
  - name: Run analysis
    continue-on-error: true # The silent killer
```

Every failure was swallowed. CI showed green. Nothing actually worked.

I had built a masterpiece of automation that automated nothing.

---

## The SOFI Disaster

On January 13, 2026 - Day 74 - I finally got the system to execute its first trades.

I chose SOFI (SoFi Technologies) because it was cheap enough for my $5,000 account. I ignored the fact that earnings were coming in 16 days. I ignored that implied volatility was at 55%. I ignored my own rules.

I put **96% of my account** into SOFI positions. Stock shares. Naked puts. No protective hedges.

Within 24 hours, I was underwater and panic-averaging down.

On January 14, I triggered an emergency exit:

- Closed all SOFI positions
- **Realized loss: $40.74**
- **Avoided potential loss: $4,800** (if SOFI crashed after earnings)

The $40.74 was tuition. The lesson was permanent.

### What I Learned From SOFI

After that loss, I did deep research on traders who started with $500-5,000 accounts:

| What They Said               | What I Was Doing        |
| ---------------------------- | ----------------------- |
| "3-5% monthly is realistic"  | Targeting 40% monthly   |
| "6+ months simulation first" | Skipped it              |
| "95% of traders fail"        | Thought I was different |
| "Process over money"         | Focused on money        |

The hardest part wasn't the $40 loss. It was admitting I had repeated every mistake that beginners make.

---

## The Math That Killed the Dream

Here's the brutal reality I finally accepted:

With a $5,000 account trading credit spreads:

- Win: Make $80
- Loss: Lose $420
- Risk/reward: 5:1 against me

To break even, I needed an **84% win rate**.

Professional options traders average 60-70% win rates.

My $100/day goal wasn't ambitious. **It was mathematically impossible.**

---

## The Pivot: Iron Condors on SPY

After weeks of research, backtesting, and studying what actually worked in my (forgotten) $100K paper account from earlier, I found the strategy that made the math work: **iron condors on SPY**.

### What's an Iron Condor?

Imagine SPY is trading at $590. You believe it will stay roughly where it is for the next month - not crash, not moon.

An iron condor lets you profit from that belief:

```
       PROFIT ZONE
          |
   $580 --|------------------- Short Put  (sell)
          |
   $575 --|------------------- Long Put   (buy for protection)
          |
          |    SPY at $590
          |
   $600 --|------------------- Short Call (sell)
          |
   $605 --|------------------- Long Call  (buy for protection)
          |
```

If SPY stays between $580 and $600 until expiration, you keep all the premium you collected. Both sides expire worthless. You win.

**The key insight:** You collect premium from BOTH sides - the put spread AND the call spread. Double the income, same amount of capital.

### Why Iron Condors Beat Credit Spreads

| Metric              | Credit Spreads           | Iron Condors (15-delta) |
| ------------------- | ------------------------ | ----------------------- |
| Win Rate            | 65-70%                   | **86%**                 |
| Risk/Reward         | 0.5:1                    | **1.5:1**               |
| TastyTrade Backtest | Lost money over 11 years | Profitable              |

The 15-delta part is important. It means you're selling options with only a 15% chance of being "in the money" at expiration. That gives you an 85%+ probability of profit before you even consider the premium you collect.

### SPY Only

After the SOFI disaster, I made a hard rule: **SPY only**.

Why?

- Best liquidity in the options market
- Tightest bid-ask spreads (less money lost to market makers)
- No earnings surprises (it's an index, not a company)
- No overnight gap risk from company news

The $100K account I had run earlier proved it: When I stuck to SPY, I made money. When I picked individual stocks like SOFI, I lost.

---

## Switching to $100,000 Paper Account

On January 30, 2026, I made a decision that felt counterintuitive: I switched from my $5,000 paper account to a **$100,000 paper account**.

Why? The math:

| Account Size | Position Limit (5%)   | Monthly Income Potential |
| ------------ | --------------------- | ------------------------ |
| $5,000       | $250 risk per trade   | ~$150/month              |
| $100,000     | $5,000 risk per trade | ~$1,600/month            |

With $100K, I could run 2-3 iron condors simultaneously without concentrating too much in any single position. The 5% position limit still applies - I just have more capital to work with.

More importantly, **$100,000 means no Pattern Day Trader restrictions**. With the $5K account, if I needed to close a position the same day I opened it, I was blocked. With $100K, I can manage positions properly.

---

## The Path to $6,000/Month

Here's the honest timeline:

| Phase      | Capital  | Monthly Income | After Tax  | When     |
| ---------- | -------- | -------------- | ---------- | -------- |
| Now        | $100,000 | ~$1,600        | ~$1,100    | Feb 2026 |
| +12 months | $250,000 | ~$4,000        | ~$2,800    | Feb 2027 |
| +18 months | $400,000 | ~$6,400        | ~$4,500    | Aug 2027 |
| +24 months | $600,000 | ~$9,600        | **$6,700** | Feb 2028 |

The key is compounding. I'm not withdrawing profits during the growth phase. Every dollar earned gets reinvested. At 8% monthly (conservative for iron condors), $100K becomes $600K in about 2 years.

At $600K with a sustainable 15% annual return: $90,000/year = **$7,500/month**.

Financial independence by age 48. Work becomes optional.

---

## The Rules I Follow Now

After 90 days of building, breaking, and rebuilding this system, I have rules I don't break:

### Pre-Trade Checklist

Before any trade executes:

1. Is it SPY? (No individual stocks)
2. Is position size 5% or less of account?
3. Is it an iron condor with defined risk on both sides?
4. Are short strikes at 15-20 delta?
5. Is expiration 30-45 days out?
6. Is stop-loss defined at 200% of credit?
7. Exit plan at 50% profit or 7 days to expiration?

Every box must be checked. No exceptions.

### Phil Town's Rule #1

Phil Town wrote a book called "Rule #1" with one central message: **Don't lose money.**

It sounds obvious, but it's not. It means:

- Never risk more than you can afford to lose
- Have a stop-loss before entering any trade
- Protect capital first, seek profits second

My 5% position limit exists because of Rule #1. Even if I'm wrong 20 times in a row (which would be statistically remarkable), I still have capital left.

---

## Lessons From the Journey

### 1. Simple Beats Complex

I built 23 workflows, 5 validation gates, sentiment analysis, multi-factor scoring. None of it mattered because a timezone bug blocked every trade.

Now I have 3 workflows. One strategy. One ticker. It works.

### 2. Paper Trade Before Real Money

The 90-day paper trading phase found 14 system bugs. Each one could have cost real money. The silent 74 days taught me more than any successful trade could have.

### 3. Record Everything

I lost $95,000 in paper trading lessons because I didn't record what the system was doing. When I finally looked at the trade history, I found proof that SPY iron condors worked beautifully - evidence I had ignored for months.

Now every trade is logged. Every lesson is recorded. No more silent failures.

### 4. Win Rate Matters More Than Win Size

A strategy that wins 86% of the time with small gains will beat a strategy that wins 50% of the time with big gains. The math is unforgiving.

### 5. Trust the Process, Not the Predictions

I can't predict where SPY will be next month. Nobody can. But I can build a system where I profit 86% of the time as long as SPY doesn't move too dramatically. That's a process I can trust.

---

## Where I Am Today

**Date:** February 1, 2026

| Metric                | Value                          |
| --------------------- | ------------------------------ |
| Paper Account         | $100,000                       |
| Strategy              | Iron Condors on SPY            |
| Position Limit        | 5% ($5,000 max risk per trade) |
| Win Rate Target       | 80%+                           |
| Monthly Income Target | $1,600                         |
| Days Until North Star | ~1,020 (November 14, 2029)     |

The system is built. The strategy is proven. The math works.

Now comes the hard part: **consistency**. Executing the same boring strategy, day after day, month after month, resisting the urge to chase bigger gains or try "just one" risky trade.

---

## The North Star

By November 14, 2029 - my 50th birthday - I will have:

- **$600,000** in trading capital (grown from $100K through disciplined compounding)
- **$6,000/month** in passive income after taxes
- **Financial independence** - the freedom to work on what matters, not what pays

This isn't a get-rich-quick scheme. It's a get-free-eventually plan.

The silent 74 days taught me that building the system is easy. Building the discipline is hard. But if I can execute one boring iron condor at a time, for the next 1,000 days, I'll be free.

And that's worth the wait.

---

_This is my journey building an AI-powered options trading system. I'm documenting everything - the failures, the lessons, and (hopefully) the eventual success. All trades are currently paper trades during the validation phase. This is not financial advice._

_Follow the journey: [GitHub](https://github.com/IgorGanapolsky/trading)_

---

*Related: [Complete Guide to AI Iron Condor Trading](/trading/2026/01/21/iron-condors-ai-trading-complete-guide/) | [The Silent 74 Days](/trading/2026/01/07/the-silent-74-days/) | [Our North Star Strategy](/trading/2026/02/17/north-star-operating-strategy/)*
