---
layout: "post"
title: "Day 86: What We Learned - January 22, 2026"
description: "Today was a wake-up call. Two critical issues surfaced that could have derailed our entire trading operation. Here's what went wrong and how we're fixing it."
date: "2026-01-22"
last_modified_at: "2026-01-22"
image: "/assets/og-image.png"
tags:
  - "lessons-learned"
  - "ai-trading"
  - "rag"
  - "building-in-public"
day_number: 86
lessons_count: 9
critical_count: 7
excerpt: "Today was a wake-up call. Two critical issues surfaced that could have derailed our entire trading operation. Here's what went wrong and how we're..."
faq: true
questions:
  - question: "What did we learn on Day 86?"
    answer: "9 lessons captured (7 critical, 0 high). Today was a wake-up call. Two critical issues surfaced that could have derailed our entire trading operation. Here's what went wrong and how we're fixing it."
  - question: "How does this system remember lessons learned?"
    answer: "We store each lesson in a RAG index and retrieve similar past incidents before future trades and engineering changes."
  - question: "Where can I browse the full code and history?"
    answer: "The full repository and daily updates are published publicly on GitHub and GitHub Pages."
---
# Day 86 of 90 | Thursday, January 22, 2026

**4 days remaining** in our journey to build a profitable AI trading system.

Today was a wake-up call. Two critical issues surfaced that could have derailed our entire trading operation. Here's what went wrong and how we're fixing it.

---

## The Hard Lessons

*These are the moments that test us. Critical issues that demanded immediate attention.*

### Position Accumulation Bug - Iron Condor Trader

iron_condor_trader.py was placing partial fills that accumulated to 8 contracts instead of max 4.

### Cumulative Position Risk Bypass - Individual Trades Accum...

1. Trade gateway `_check_position_size_risk()` only checked **individual trade risk**

**Key takeaway:** Trade 1: $500 risk (10.

### Crisis Mode Failure Analysis - Jan 22, 2026

The AI trading system failed catastrophically over three days (Jan 20-22, 2026):

### Alpaca API Bug - Close Position Treated as Opening Cash-S...

When attempting to SELL TO CLOSE a LONG put position, Alpaca API treats it as OPENING a new short position (cash-secured put), requiring $113,000 buying power:

**Key takeaway:** **MANUAL ACTION REQUIRED** - CEO must close position directly via:

### Alpaca API Treats Close as Open for Options

```

**Key takeaway:** Unable to Close Positions](https://forum.

### Use close position() API for Closing Orphan Positions

When closing options positions via Alpaca API, use `client.close_position(symbol)` instead of `client.submit_order(MarketOrderRequest(...))`. The `close_position()` method automatically handles:

**Key takeaway:** 1. Replace `submit_order(MarketOrderRequest(...))` with `close_position(symbol)`:

### CTO Failure Crisis - Third Day of Losses

Three consecutive days of losses. Total P/L: **-$413.39 (-8.27%)** from $5,000 starting balance.

**Key takeaway:** We lost $413.


## Quick Wins & Refinements

- **Position Accumulation Crisis - 8 Contracts Instead of Max 4** - On January 21-22, 2026, 8 contracts of SPY260220P00658000 accumulated when the maximum allowed was 4...
- **Alpaca API Bug - Close Position Treated as New Short** - When attempting to close a LONG put position (SPY260220P00658000, 8 contracts), Alpaca's API returne...


---

## Today's Numbers

| What | Count |
|------|-------|
| Lessons Learned | **9** |
| Critical Issues | 7 |
| High Priority | 0 |
| Improvements | 2 |

---

## Tech Stack Behind the Lessons

Every lesson we learn is captured, analyzed, and stored by our AI infrastructure:

<div class="mermaid">
flowchart LR
    subgraph Learning["Learning Pipeline"]
        ERROR["Error/Insight<br/>Detected"] --> CLAUDE["Claude Opus<br/>(Analysis)"]
        CLAUDE --> RAG["LanceDB RAG<br/>(Storage)"]
        RAG --> BLOG["GitHub Pages<br/>(Publishing)"]
        BLOG --> DEVTO["Dev.to<br/>(Distribution)"]
    end
</div>

### How We Learn Autonomously

| Component | Role in Learning |
|-----------|------------------|
| **Claude Opus 4.5** | Analyzes errors, extracts insights, determines severity |
| **LanceDB RAG** | Stores lessons with 768D embeddings for semantic search |
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

## FAQ

### What did we learn today?

9 lessons captured (7 critical, 0 high). Today was a wake-up call. Two critical issues surfaced that could have derailed our entire trading operation. Here's what went wrong and how we're fixing it.

### How do you keep these lessons from getting lost?

We index every lesson into a RAG corpus and query it before new trades and major engineering changes.

### Where is the canonical version of this post?

This post's canonical URL is https://igorganapolsky.github.io/trading/2026/01/22/lessons-learned/.

*Day 86/90 complete. 4 to go.*
