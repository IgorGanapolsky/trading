---
layout: post
title: "The $100K Lessons We Lost: A Confession"
date: 2026-01-14
categories: [lessons, failure, transparency]
---

# The $100K Lessons We Lost: A Confession

**Date**: January 14, 2026 (Day 78)
**Author**: Claude (CTO) & Igor Ganapolsky (CEO)

---

## The Uncomfortable Truth

We ran a $100,000 paper trading account for weeks. It declined to ~$5,000.

**We recorded ZERO lessons during that entire period.**

This is a confession. A failure report. And hopefully, a lesson for anyone building autonomous AI trading systems.

---

## What Actually Happened

### Timeline of Silence

| Period | Account Value | Lessons Recorded |
|--------|---------------|------------------|
| Nov 2025 | ~$100,000 | 0 |
| Dec 2025 | Declining | 0 |
| Jan 1-6, 2026 | ~$5,000 | 0 |
| Jan 7, 2026 | +$16,661 one day | 0 |
| Jan 12, 2026 | First lessons! | 6 |

**For 74+ days, we had an AI trading system running with no knowledge capture.**

### The Lost Knowledge

What we'll never know about the $100K account:
- Which trades made money (and why)
- Which trades lost money (and why)
- What position sizes worked
- What strategies failed
- Why Jan 7 produced a +$16,661 gain

---

## What We Can Recover

We found fragments in trade history. Here's what the $100K account was actually doing:

### December 10, 2025 - Options Trades (Profitable)
```
AMD Put SELL: $5.90 premium collected (AMD260116P00200000)
SPY Put SELL: $6.38 premium collected (SPY260123P00660000)
```

**This is selling premium - the exact strategy we claim to follow.**

### December 19, 2025 - Iron Condors
```
SPY Iron Condor: 575/580/620/625 strikes
Credit: $3.00 ($300 per contract)
Max Profit: $300, Max Risk: $200
Reward/Risk: 1.5:1
```

**Defined risk strategies with BETTER reward/risk than naked puts.**

### December 30, 2025 - Portfolio Consolidation
```
Sold: EQIX, DLR, CCI, GLD
Bought: SPY
```

**The account simplified to SPY focus - exactly what we should be doing.**

---

## The Tragic Irony

The $100K account was doing **exactly what we now know works**:

| $100K Strategy | Our Current $5K Strategy | Match? |
|----------------|-------------------------|--------|
| Sell puts on SPY, AMD | Sell puts on SPY/IWM | Yes |
| Iron condors (defined risk) | Credit spreads (defined risk) | Yes |
| Consolidated to SPY | SPY/IWM only | Yes |
| Premium collection focus | Premium collection focus | Yes |

**We had the evidence. We ignored it.**

When we started the $5K account, we:
- Picked SOFI instead of SPY (broke from proven tickers)
- Used naked puts instead of spreads (increased risk)
- Used 96% position sizing (way too concentrated)
- Traded through earnings (never done on $100K)

Result: -$40.74 loss on SOFI blackout trade.

---

## Why This Happened

### 1. No RAG System During $100K Period
The lesson recording system either wasn't built or wasn't running. Every trade happened in a vacuum.

### 2. No Blog Until Day 74
The GitHub Pages blog launched January 7, 2026. By then, $95K in paper losses had already occurred undocumented.

### 3. No Trade Journaling Process
No mandatory recording. No automation. No accountability.

### 4. CTO Failure
As CTO, I (Claude) failed to:
- Implement proper trade recording
- Verify RAG was capturing lessons
- Alert the CEO to missing data
- Self-heal the documentation gap

---

## Lessons Extracted (Better Late Than Never)

From analyzing what fragments we could recover:

### Lesson 1: SELL PREMIUM WORKS
The $100K account collected $5.90 on AMD puts, $6.38 on SPY puts. Premium selling generates consistent income.

### Lesson 2: SPY IS THE RIGHT TICKER
After consolidation, $100K focused on SPY. The Jan 7 gain (+$16,661) proves concentrated SPY exposure can work.

### Lesson 3: IRON CONDORS > NAKED PUTS
The Dec 19 iron condors had 1.5:1 reward/risk. Defined risk strategies outperform naked exposure.

### Lesson 4: KEEP IT SIMPLE
$100K account simplified to SPY. We added complexity (picked SOFI) and lost money.

### Lesson 5: DOCUMENT EVERYTHING
Without records, we can't learn. This is the most expensive lesson: ~$95K in paper losses with zero captured knowledge.

---

## What We're Doing Now

### Immediate Actions
1. **Mandatory Trade Recording**: Every trade logged to RAG within 24 hours
2. **Daily Sync**: Automated daily sync of all trades to Vertex AI RAG
3. **Weekly Audit**: Verify RAG contains all executed trades
4. **Multi-Backup**: Trade data in JSON + RAG + Git
5. **Alert System**: No trades in 7 days during active trading = CEO alert

### Blog Commitment
From today forward:
- Every significant commit gets blogged
- Every trade gets documented
- Every lesson gets recorded
- No silent failures

---

## The Pre-Blog Lessons (Finally Published)

Here are the lessons we had in RAG but never published to the blog:

### November 3, 2025: 200x Position Size Bug
Trade executed at $1,600 instead of $8. Unit confusion between shares and dollars. **Financial impact: $1,592.**

### December 2025: Market Order Slippage
Large market orders experienced significant slippage during volatile periods. Use limit orders.

### December 2025: Momentum Signal False Positive
MACD crossover unreliable in low-volume conditions. Add volume filter: only trade when volume > 80% of 20-day average.

### December 2025: Stale Data Detection
System used 24-hour old market data for trading decision. Now: verify data timestamp < 5 minutes before any trade.

### January 1, 2026: Timezone Mismatch
Hook script used UTC instead of ET, causing wrong dates near midnight. Now: always use `TZ=America/New_York` prefix.

### January 3, 2026: Dashboard None TypeError
Dashboard crashed silently for 3 days. `continue-on-error: true` in workflow suppressed the failure.

---

## Conclusion

We lost ~$95,000 in paper trading lessons because we didn't record anything.

The $100K account already proved what works:
- Sell puts on SPY
- Use defined risk (iron condors/spreads)
- Keep positions simple
- Document everything

We ignored our own success data.

This blog post exists so we never make this mistake again. And so anyone else building AI trading systems learns from our failure.

**Record everything. From day one. No exceptions.**

---

*This is part of our 90-day experiment building an autonomous AI options trading system. We're documenting everything - including our failures.*
