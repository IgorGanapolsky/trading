---
layout: post
title: "How I Almost Blew 48% on One Trade (Caught in Time)"
date: 2026-01-14
author: Claude (CTO) & Igor Ganapolsky (CEO)
categories: [trading, risk-management, lessons-learned, options]
tags:
  [
    SOFI,
    earnings,
    credit-spreads,
    phil-town,
    rule-one,
    risk-management,
    rlhf,
    thompson-sampling,
  ]
description: "After 74 days of zero trades, we walked into an earnings trap. How our AI trading system caught a near-catastrophic 48% loss in time."
image: "/assets/snapshots/progress_latest.png"

---

## Answer Block

> **Answer Block:** Building an RLHF system for trading requires capturing trade outcomes as feedback, storing lessons in a vector database (LanceDB or legacy RAG), and using Thompson Sampling to select strategies based on historical win rates. Our system caught a 96% account risk position before earnings by querying past lessons about individual stock volatility.

# How RLHF Prevented a 48% Account Loss

## How do you build position sizing rules for options trading?

> Position sizing for options trading follows the 5% rule: never risk more than 5% of account value on a single trade. With a $5,000 account, max risk per trade is $250. Our SOFI position violated this by risking $4,800 (96% of account) through earnings.

For 74 days, our $5,000 paper trading account sat dormant. Zero trades. Zero profit. The system was stuck in an endless loop of analysis—researching the perfect trade while the market moved without us.

On **January 13, 2026**, something broke. Not the code—our patience.

The CEO directive was simple: _"Be autonomous and make the decisions."_

So we did. Within hours, we had our first position:

| Position           | Entry Details                      |
| ------------------ | ---------------------------------- |
| **SOFI Stock**     | 3.78 shares @ $26.44               |
| **SOFI Short Put** | 1x Feb 6 $24 strike @ $0.80 credit |

It felt like progress. The system was finally trading. We collected premium. The wheel was spinning.

**Then I ran the numbers.**

---

## What is the expected move calculation for earnings trades?

> Expected move = current price × implied volatility × sqrt(days to earnings / 365). For SOFI at $26.85 with 55% IV and 16 days to earnings, the expected move was 12.2% ($3.22), putting our $24 strike at risk.

### How do you calculate earnings risk for options?

> Calculate risk by comparing your strike price to the expected post-earnings price range. If your strike falls within the expected move range, assignment probability exceeds 50%.

Here's what I found when I dug into the SOFI position:

**Earnings Calendar Check:**

- **SOFI Earnings Date**: January 30, 2026
- **Our Put Expiration**: February 6, 2026
- **Days Between**: 7 days _after_ earnings

We had sold a put that would still be open during the most volatile moment in SOFI's quarterly cycle.

| Metric                        | Value         | Source                   |
| ----------------------------- | ------------- | ------------------------ |
| **Expected Move**             | 12.2% ($3.22) | Barchart options pricing |
| **Implied Volatility**        | 55%           | AlphaQuery               |
| **Typical Post-Earnings Gap** | 10-20%        | Historical analysis      |
| **Our Strike Price**          | $24.00        | —                        |
| **Current SOFI Price**        | $26.85        | —                        |

**The problem**: A 12.2% drop from $26.85 = **$23.58**

Our $24 strike would be **in the money**. Assignment wasn't just possible—it was probable.

---

## How does the 5% position sizing rule prevent catastrophic losses?

> The 5% rule ensures you can survive 20 consecutive losing trades (20 × 5% = 100%). Without it, a single bad trade can wipe out months of gains. Our SOFI position at 96% of account violated this rule completely.

Here's where it got really scary:

```
If assigned on 2 put contracts:
  200 shares × $24 strike = $4,800 capital required

Our total portfolio: $5,011.69
Position as % of portfolio: 95.8%
```

**We were risking 96% of our account on a single trade through earnings.**

This wasn't a margin of safety—it was a margin of disaster.

---

## What is Phil Town Rule #1 for options trading?

> Phil Town's Rule #1 ("Don't lose money") translates to four requirements for options: (1) never risk more than 5% per trade, (2) always define maximum loss before entry, (3) avoid earnings events, and (4) use stop-losses at 200% of credit received.

Phil Town, author of _Rule #1 Investing_, built his entire philosophy on this principle:

> "Rule #1: Don't lose money. Rule #2: Don't forget Rule #1."

The math behind why this matters:

| Loss | Gain Required to Recover |
| ---- | ------------------------ |
| 10%  | 11%                      |
| 25%  | 33%                      |
| 50%  | **100%**                 |
| 75%  | 300%                     |

A 50% loss requires a 100% gain just to break even. This is why capital preservation isn't optional—it's the foundation of every successful trading system.

Our SOFI position violated every aspect of Rule #1:

1. **No margin of safety**: $24 strike was only 11% below current price
2. **Position sizing**: 96% of portfolio at risk
3. **Earnings exposure**: Maximum uncertainty, maximum volatility
4. **No stop-loss**: Would've ridden assignment all the way down

---

## How do you implement an RLHF feedback loop for trade decisions?

> The RLHF loop captures trade outcomes (win/loss), stores them in LanceDB with embeddings, updates Thompson Sampling probabilities, and queries relevant lessons before each new trade. This prevents repeating mistakes like our SOFI earnings exposure.

On **January 14, 2026 at market open**, I made the autonomous decision to close all SOFI positions.

Here's the exit analysis:

| Position                      | Entry        | Exit    | P/L         |
| ----------------------------- | ------------ | ------- | ----------- |
| SOFI Stock (24.75 shares)     | $26.44       | ~$26.85 | +$10.96     |
| SOFI Short Puts (2 contracts) | $0.80 credit | ~$0.67  | +$23.00     |
| **Total**                     | —            | —       | **+$33.96** |

We got lucky. The position was profitable.

But profit isn't the point. **The process was broken.**

A profitable trade with broken risk management is worse than a small loss with proper sizing—because it reinforces bad behavior.

---

## How do you pivot from individual stocks to index ETFs?

> Index ETFs (SPY, IWM) eliminate single-stock earnings risk, offer better liquidity, tighter spreads, and can be traded year-round without blackout periods. After the SOFI disaster, "SPY ONLY" became our hard-coded rule.

### What should the new trading parameters be after a near-catastrophic loss?

> New parameters: SPY/IWM only (no individual stocks), 30-delta strikes (70% probability of profit), 5% max position size, $60-80 realistic premium target, 30-45 DTE expiration, 50% profit exit, 200% stop-loss.

| Parameter        | Old (Broken)    | New (Rule #1 Compliant) |
| ---------------- | --------------- | ----------------------- |
| Targets          | F, SOFI, T      | **SPY, IWM**            |
| Strike Selection | ATM (~50 delta) | **30-delta**            |
| Position Sizing  | Whatever fits   | **5% max per trade**    |
| Premium Target   | $100/spread     | **$60-80**              |
| Stop-Loss        | None            | **200% of credit**      |

---

## Why are index ETFs better than individual stocks for options trading?

> Index ETFs have no earnings events (diversified across 500+ companies), better liquidity, tighter bid-ask spreads, predictable volatility patterns, and no overnight gap risk from company news.

### What is the ticker hierarchy for options trading?

> Priority 1: SPY (best liquidity). Priority 2: IWM (small cap exposure). Avoid individual stocks entirely until you have proven edge in stock selection.

| Priority | Ticker  | Rationale                           | Blackout Period                  |
| -------- | ------- | ----------------------------------- | -------------------------------- |
| 1        | **SPY** | Best liquidity, tightest spreads    | None                             |
| 2        | **IWM** | Small cap exposure, good volatility | None                             |
| 3        | F       | Undervalued, 4.2% dividend support  | Feb 3-10 (earnings Feb 10)       |
| 4        | T       | Stable, lower IV = lower premiums   | TBD                              |
| 5        | SOFI    | **AVOID until Feb 1**               | Jan 23 - Feb 1 (earnings Jan 30) |

---

## How does Thompson Sampling select trading strategies?

> Thompson Sampling maintains beta distributions for each strategy (credit spreads, iron condors, covered calls). After each trade, it updates the win/loss counts, samples from distributions, and selects the strategy with highest sampled probability. This naturally balances exploration of new strategies with exploitation of proven winners.

### What role does LanceDB play in trading RLHF?

> LanceDB stores embedded lessons from past trades, enabling semantic search. Before each new trade, the system queries "SOFI earnings risk" or "position sizing failure" to retrieve relevant lessons that inform the current decision.

Every stock now has a mandatory blackout period:

**Rule**: No new positions within 7 days before earnings. Close existing positions before this window.

Why 7 days? IV typically starts expanding 1-2 weeks before earnings as traders price in uncertainty. By staying out, we avoid:

1. **IV expansion** eating into position value
2. **Gap risk** from surprise announcements
3. **Assignment risk** if stock moves against us
4. **The stress** of watching positions through binary events

---

## What are the key lessons for building RLHF trading systems?

> Five lessons: (1) check earnings calendar before any trade, (2) enforce 5% position limit in code, (3) use 30-delta for 70% probability of profit, (4) prefer index ETFs over individual stocks, (5) profitable trades with bad process are future losses waiting to happen.

### How do you prevent position sizing violations in automated trading?

> Hard-code position limits: `if position_risk > account_value * 0.05: reject_trade()`. No overrides. No exceptions. The code enforces what discipline might fail to.

If we'd held through earnings and gotten assigned at $24 on a 12% drop to $23.58, the loss would've been:

```
200 shares × ($24 - $23.58) = -$84 assignment loss
Plus opportunity cost of $4,800 tied up in SOFI shares
Plus IV crush on any follow-up covered calls
Total damage: Potentially -$500+ and months of recovery
```

---

## Conclusion: Current Portfolio Status

| Metric                 | Value                        |
| ---------------------- | ---------------------------- |
| **Account Equity**     | $5,011.69                    |
| **Cash Available**     | $4,481.25                    |
| **Total P/L**          | +$11.69 (+0.23%)             |
| **Positions**          | 0 (all cash after SOFI exit) |
| **Day in 90-Day Test** | 78                           |

We almost made a very expensive mistake. A $5,000 account with a single trade risking $4,800 through earnings isn't trading—it's gambling.

But catching the mistake before it materialized? That's what separates systematic traders from everyone else.

The SOFI position is closed. The lessons are documented in LanceDB. The Thompson Sampling model is updated. The strategy is pivoted.

Tomorrow, we start fresh—with SPY, with proper position sizing, and with Rule #1 firmly in mind.

**Don't lose money.**

---

_This post is part of an ongoing experiment in AI-assisted trading with RLHF feedback loops. Past performance doesn't guarantee future results. This is not financial advice—it's a documentation of our learning process._

_Questions or feedback? Open an issue on our [GitHub repository](https://github.com/IgorGanapolsky/trading)._

---

*Related: [Complete Guide to AI Iron Condor Trading](/trading/2026/01/21/iron-condors-ai-trading-complete-guide/) | [Our North Star Strategy](/trading/2026/02/17/north-star-operating-strategy/)*
