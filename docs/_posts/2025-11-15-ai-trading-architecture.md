---
layout: post
title: "The 4-Gate Trading Architecture: How Our AI Makes Decisions"
date: 2025-11-15
categories: [technical, architecture]
tags: [trading-system, gates, risk-management, ai-architecture]
description: "A deep dive into our 4-gate trading architecture where every trade must pass momentum, sentiment, risk, and execution gates."
---

# How Our AI Decides to Trade

Every trade in our system must pass through 4 gates. If any gate rejects, no trade happens.

This is how we enforce discipline without emotion.

## The 4-Gate Funnel

```
Signal Detected
      ↓
┌─────────────┐
│  GATE 1     │ ← Momentum: Is the trend in our favor?
│  Momentum   │
└─────────────┘
      ↓ PASS
┌─────────────┐
│  GATE 2     │ ← Sentiment: What's the market saying?
│  Sentiment  │
└─────────────┘
      ↓ PASS
┌─────────────┐
│  GATE 3     │ ← Risk: Can we afford this trade?
│  Risk       │
└─────────────┘
      ↓ PASS
┌─────────────┐
│  GATE 4     │ ← Execute: Place the order
│  Execution  │
└─────────────┘
      ↓
   TRADE PLACED
```

## Gate 1: Momentum

**Question**: Is the technical setup favorable?

**What it checks**:
- MACD crossover direction
- RSI (avoid overbought/oversold extremes)
- Volume confirmation
- Price relative to moving averages

**Rejection example**:
```
REJECTED: RSI at 78 (overbought)
Reason: Selling puts when stock is overbought increases assignment risk
```

## Gate 2: Sentiment

**Question**: What's the market sentiment?

**What it checks**:
- News sentiment (positive/negative/neutral)
- Social media mentions
- Analyst ratings changes
- Earnings proximity

**Rejection example**:
```
REJECTED: Negative sentiment score -0.45
Reason: Multiple negative news articles in last 24h
```

## Gate 3: Risk

**Question**: Does this trade fit our risk parameters?

**What it checks**:
- Position size vs account (max 20%)
- Daily loss limit (max 2%)
- Correlation with existing positions
- Buying power requirements

**Rejection example**:
```
REJECTED: Position too large
Required: $1,500 (30% of account)
Max allowed: $1,000 (20% of account)
```

## Gate 4: Execution

**Question**: Can we get a good fill?

**What it checks**:
- Bid-ask spread (max 5%)
- Liquidity (minimum volume)
- Market hours (no after-hours)
- Order type selection

**Rejection example**:
```
REJECTED: Spread too wide
Bid: $0.05, Ask: $0.15 (200% spread)
Max allowed: 5%
```

## Why 4 Gates?

**Defense in depth**. Any single check can be wrong. Four independent checks dramatically reduce bad trades.

Consider the math:
- Each gate has 90% accuracy
- Single gate: 10% bad trades
- Four gates: 0.01% bad trades (0.1 × 0.1 × 0.1 × 0.1)

## Real Example

**Trade**: Sell SOFI $5 put, Jan 17 expiry

| Gate | Check | Result |
|------|-------|--------|
| Momentum | RSI: 52, MACD: Bullish | ✅ PASS |
| Sentiment | Score: +0.23 | ✅ PASS |
| Risk | $500 / $5000 = 10% | ✅ PASS |
| Execution | Spread: 3% | ✅ PASS |

**Outcome**: Trade executed at $0.12 premium

## The Code

```python
class TradingGatePipeline:
    def evaluate(self, trade):
        gates = [
            self.gate1_momentum,
            self.gate2_sentiment,
            self.gate3_risk,
            self.gate4_execution
        ]

        for gate in gates:
            result = gate.check(trade)
            if result.status == "REJECT":
                logger.info(f"Trade rejected at {gate.name}: {result.reason}")
                return None

        return self.execute(trade)
```

## What We've Learned

After 74 days:
- **Gate 1 rejects**: 45% of signals (momentum not confirmed)
- **Gate 2 rejects**: 20% of remaining (sentiment negative)
- **Gate 3 rejects**: 15% of remaining (risk too high)
- **Gate 4 rejects**: 5% of remaining (execution issues)

Only ~35% of initial signals become trades. That's the point.

## The Human Element

I (Igor) can override any gate. But I rarely do.

The system is more disciplined than I am. That's why I built it.

---

*Architecture documented across multiple lessons. [See all lessons](/trading/lessons/)*
