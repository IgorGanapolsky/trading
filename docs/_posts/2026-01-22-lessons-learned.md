---
layout: post
title: "Day 86: What We Learned - January 22, 2026"
date: 2026-01-22
day_number: 86
lessons_count: 10
critical_count: 3
excerpt: "Crisis mode activated: Alpaca API bug prevents closing positions, PDT locks $5K account. We pivoted to $100K account and placed iron condor. Here's the full story..."
---

# Day 86 of 90 | Thursday, January 22, 2026

**4 days remaining** in our journey to build a profitable AI trading system.

Today was crisis mode. We discovered a critical Alpaca API bug that prevented us from closing positions, combined with PDT restrictions that locked our $5K account. Here's how we navigated it.

---

## The Hard Lessons

*These are the moments that test us. Critical issues that demanded immediate attention.*

### LL-291: Alpaca API Bug - Close Position Treated as New Short (CRITICAL)

When attempting to close a LONG put position (SPY260220P00658000, 8 contracts), Alpaca's API returned:
- Error: "insufficient options buying power for cash-secured put (required: $113,000, available: $2,607)"

**The bug:** Alpaca incorrectly treats SELL-to-close as a NEW short (cash-secured put), requiring massive collateral instead of simply closing the existing long position.

**What we tried (ALL FAILED):**
1. Market order via Python SDK
2. Limit order
3. close_position() endpoint
4. Direct REST API with position_intent='sell_to_close'
5. DELETE /v2/positions/{symbol}
6. close_all_positions()
7. Partial close (1 contract)
8. Account config: closing_transactions_only=True
9. Account config: pdt_check='exit'

**Resolution:** Pivoted to $100K paper account (PDT-enabled, $268K buying power) and successfully placed iron condor:
- Put spread: Sell 660, Buy 655 @ $0.43 credit
- Call spread: Sell 720, Buy 725 @ $0.38 credit
- Total credit: $81/contract, Max risk: $419

**Key takeaway:** Always have a backup account. PDT-enabled accounts (>$25K) avoid the day-trading trap.

### SOFI Loss Realized - Jan 14, 2026

1. SOFI stock + CSP opened Day 74 (Jan 13)

**Key takeaway:** System allowed trade despite CLAUDE.

### SOFI Position Held Through Earnings Blackout

SOFI CSP (Feb 6 expiration) was held despite Jan 30 earnings date approaching.

**Key takeaway:** Put option loss: -$13.


## Important Discoveries

*Not emergencies, but insights that will shape how we trade going forward.*

### Trade Data Source Priority Bug - Webhook Missing Alpaca Data

**Status**: FIXED

### Iron Condor Win Rate Improvement Research

Current win rate is 33.3% (2/6 trades) vs target 80%+. Need to improve.

### Iron Condor Entry Signals & Timing

System not generating enough trade signals. Need clear entry criteria.


## Quick Wins & Refinements

- **Memgraph Graph Database Evaluation - FLUFF** - LL-267: Memgraph Graph Database Evaluation - FLUFF

Date: January 21, 2026
Category: RAG / Resource ...
- **Deep Operational Integrity Audit - 14 Issues Found** - LL-240: Deep Operational Integrity Audit - 14 Issues Found

 Date
January 16, 2026 (Friday, 6:00 PM ...
- **Phil Town Valuations - December 2025** - This lesson documents Phil Town valuations generated on December 4, 2025 during the $100K paper trad...
- **Theta Scaling Plan - December 2025** - This lesson documents the theta scaling strategy from December 2, 2025 when account equity was $6,00...


---

## Today's Numbers

| What | Count |
|------|-------|
| Lessons Learned | **10** |
| Critical Issues | 3 |
| High Priority | 3 |
| Improvements | 4 |

### Crisis Summary
- **$5K Account:** LOCKED (PDT + API bug) - 4 positions trapped
- **$100K Account:** Active - Iron condor placed, $81 credit collected
- **Lesson:** PDT-enabled accounts (>$25K) are essential for options trading

---

## Tech Stack Behind the Lessons

Every lesson we learn is captured, analyzed, and stored by our AI infrastructure:

<div class="mermaid">
flowchart LR
    subgraph Learning["Learning Pipeline"]
        ERROR["Error/Insight<br/>Detected"] --> CLAUDE["Claude Opus<br/>(Analysis)"]
        CLAUDE --> RAG["Vertex AI RAG<br/>(Storage)"]
        RAG --> BLOG["GitHub Pages<br/>(Publishing)"]
        BLOG --> DEVTO["Dev.to<br/>(Distribution)"]
    end
</div>

### How We Learn Autonomously

| Component | Role in Learning |
|-----------|------------------|
| **Claude Opus 4.5** | Analyzes errors, extracts insights, determines severity |
| **Vertex AI RAG** | Stores lessons with 768D embeddings for semantic search |
| **Gemini 2.0 Flash** | Retrieves relevant past lessons before new trades |
| **OpenRouter (DeepSeek)** | Cost-effective sentiment analysis and research |

### Why This Matters

1. **No Lesson Lost**: Every insight persists in our RAG corpus
2. **Contextual Recall**: Before each trade, we query similar past situations
3. **Continuous Improvement**: 200+ lessons shape every decision
4. **Transparent Journey**: All learnings published publicly

*[Full Tech Stack Documentation](/trading/tech-stack/)*

---

## The Journey So Far

We're building an autonomous AI trading system that learns from every mistake. This isn't about getting rich quick - it's about building a system that can consistently generate income through disciplined options trading.

**Our approach:**
- Paper trade for 90 days to validate the strategy
- Document every lesson, every failure, every win
- Use AI (Claude) as CTO to automate and improve
- Follow Phil Town's Rule #1: Don't lose money

Want to follow along? Check out the [full project on GitHub](https://github.com/IgorGanapolsky/trading).

---

*Day 86/90 complete. 4 to go.*
