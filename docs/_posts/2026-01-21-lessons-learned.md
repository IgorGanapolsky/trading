---
layout: post
title: "Day 85: What We Learned - January 21, 2026"
date: 2026-01-21
day_number: 85
lessons_count: 16
critical_count: 6
excerpt: "Today was a wake-up call. Two critical issues surfaced that could have derailed our entire trading operation. Here's what went wrong and how we're fix..."
---

# Day 85 of 90 | Wednesday, January 21, 2026

**5 days remaining** in our journey to build a profitable AI trading system.

Today was a wake-up call. Two critical issues surfaced that could have derailed our entire trading operation. Here's what went wrong and how we're fixing it.

---

## The Hard Lessons

*These are the moments that test us. Critical issues that demanded immediate attention.*

### SOFI Position Held Through Earnings Blackout

SOFI CSP (Feb 6 expiration) was held despite Jan 30 earnings date approaching.

**Key takeaway:** Put option loss: -$13.

### CTO Failure - Stale Data Led to Misinformation

CTO (Claude) gave CEO incorrect P/L information multiple times:

**Key takeaway:** Claimed $0.

### Position Imbalance Crisis - Orphan Long Puts

Portfolio lost $329.42 (-6.59%) due to position imbalance:

**Key takeaway:** The orphan longs are decaying and losing money without corresponding short premium to offset.

### Strategy Violation Crisis - Multiple Rogue Workflows

On Jan 21, 2026, the trading system LOST $70.13 due to executing trades that VIOLATE CLAUDE.md strategy mandate. The system bought SPY SHARES and SOFI OPTIONS when it should ONLY execute iron condors 

**Key takeaway:** Portfolio: $5,028.

### SOFI Position Blocked All Trading - Buying Power Crisis

1. SOFI260213P00032000 (short put) was open with -$685 market value

**Key takeaway:** 1. Triggered `close-non-spy-positions.yml` workflow

### SOFI Loss Realized - Jan 14, 2026

1. SOFI stock + CSP opened Day 74 (Jan 13)

**Key takeaway:** System allowed trade despite CLAUDE.


## Important Discoveries

*Not emergencies, but insights that will shape how we trade going forward.*

### Trade Data Source Priority Bug - Webhook Missing Alpaca Data

**Status**: FIXED

### RAG Testing Evaluation - Retrieval Accuracy and Grounding

LL-268: RAG Testing Evaluation - Retrieval Accuracy and Grounding

ID: LL-268
Date: 2026-01-21
Severity: HIGH
Category: Testing

 Summary
Evaluated Medium article "RAG Testing — Validating Retrieval

### Iron Condor Optimization Research - 86% Win Rate Strategy

LL-277: Iron Condor Optimization Research - 86% Win Rate Strategy

Date: January 21, 2026
Category: strategy, research, optimization
Severity: HIGH

 Source
- Options Trading IQ: Iron Condor Success


## Quick Wins & Refinements

- **Day 2 Crisis - Position Imbalance and Missing CALL Legs** - Two consecutive days of trading crises:...
- **RAG Without Vectors - Article Evaluation** - Evaluated article: "You Probably Don't Need a Vector Database for Your RAG — Yet" (Towards Data Scie...
- **Deep Operational Integrity Audit - 14 Issues Found** - LL-240: Deep Operational Integrity Audit - 14 Issues Found

 Date
January 16, 2026 (Friday, 6:00 PM ...
- **Phil Town Valuations - December 2025** - This lesson documents Phil Town valuations generated on December 4, 2025 during the $100K paper trad...


---

## Today's Numbers

| What | Count |
|------|-------|
| Lessons Learned | **16** |
| Critical Issues | 6 |
| High Priority | 3 |
| Improvements | 7 |

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

*Day 85/90 complete. 5 to go.*
