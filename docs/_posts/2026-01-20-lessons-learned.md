---
layout: post
title: "Day 84: What We Learned - January 20, 2026"
date: 2026-01-20
day_number: 84
lessons_count: 6
critical_count: 3
excerpt: "Today was a wake-up call. Two critical issues surfaced that could have derailed our entire trading operation. Here's what went wrong and how we're fix..."
---

# Day 84 of 90 | Tuesday, January 20, 2026

**6 days remaining** in our journey to build a profitable AI trading system.

Today was a wake-up call. Two critical issues surfaced that could have derailed our entire trading operation. Here's what went wrong and how we're fixing it.

---

## The Hard Lessons

*These are the moments that test us. Critical issues that demanded immediate attention.*

### Trading Crisis - System Stuck for 7 Days

-

### CI Failure Due to Legacy SOFI Position

1. CI failed at 15:41 UTC with test `test_positions_are_spy_only` failing

**Key takeaway:** CLAUDE.

### System Blocked But No Auto-Cleanup Mechanism

The trading system correctly blocked new trades due to 30% risk exposure (3 spreads when max is 1), but there was NO automated mechanism to close excess positions. Result: **0 trades on Jan 20, 2026**

**Key takeaway:** If a system can detect a violation, it must also have an automated path to RESOLVE that violation.


## Important Discoveries

*Not emergencies, but insights that will shape how we trade going forward.*

### SOFI PDT Crisis - SPY ONLY Violation

A SOFI short put position (SOFI260213P00032000) was opened at 14:35 UTC, violating the "SPY ONLY" directive in CLAUDE.md. The position is now -$150 unrealized and cannot be closed until tomorrow due t

### PDT Protection Blocks SOFI Position Close

SOFI260213P00032000 (short put) cannot be closed due to PDT (Pattern Day Trading) protection.


## Quick Wins & Refinements

- **Exceptional Daily Profit - Strategy Validated** - LL-271: Exceptional Daily Profit - Strategy Validated

 Date
January 20, 2026

 Category
SUCCESS / S...


---

## Today's Numbers

| What | Count |
|------|-------|
| Lessons Learned | **6** |
| Critical Issues | 3 |
| High Priority | 2 |
| Improvements | 1 |

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

*Day 84/90 complete. 6 to go.*
