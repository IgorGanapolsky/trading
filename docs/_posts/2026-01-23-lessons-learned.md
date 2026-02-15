---
layout: "post"
title: "Day 87: What We Learned - January 23, 2026"
description: "Today was a wake-up call. Two critical issues surfaced that could have derailed our entire trading operation. Here's what went wrong and how we're fixing it."
date: "2026-01-23"
last_modified_at: "2026-01-23"
image: "/assets/og-image.png"
tags:
  - "lessons-learned"
  - "ai-trading"
  - "rag"
  - "building-in-public"
day_number: 87
lessons_count: 5
critical_count: 2
excerpt: "Today was a wake-up call. Two critical issues surfaced that could have derailed our entire trading operation. Here's what went wrong and how we're..."
faq: true
questions:
  - question: "What did we learn on Day 87?"
    answer: "5 lessons captured (2 critical, 1 high). Today was a wake-up call. Two critical issues surfaced that could have derailed our entire trading operation. Here's what went wrong and how we're fixing it."
  - question: "How does this system remember lessons learned?"
    answer: "We store each lesson in a RAG index and retrieve similar past incidents before future trades and engineering changes."
  - question: "Where can I browse the full code and history?"
    answer: "The full repository and daily updates are published publicly on GitHub and GitHub Pages."
---
# Day 87 of 90 | Friday, January 23, 2026

**3 days remaining** in our journey to build a profitable AI trading system.

Today was a wake-up call. Two critical issues surfaced that could have derailed our entire trading operation. Here's what went wrong and how we're fixing it.

---

## The Hard Lessons

*These are the moments that test us. Critical issues that demanded immediate attention.*

### Ll 298 Share Churning Loss

Lost $22.61 on January 23, 2026 from 49 SPY share trades instead of iron condor execution.

### Invalid Option Strikes Causing CALL Legs to Fail

Iron condor CALL legs were not executing because calculated strikes ($724, $729) were invalid. SPY options have $5 strike increments for OTM options, so only $720, $725, $730, etc. exist.


## Important Discoveries

*Not emergencies, but insights that will shape how we trade going forward.*

### Iron Condor Position Management System Implementation

Created dedicated iron condor position management system with proper exit rules based on LL-268/LL-277 research. This addresses a critical gap where the existing `manage_positions.py` used equity-base


## Quick Wins & Refinements

- **ML/RAG Integration Analysis and Implementation** - LL-302: ML/RAG Integration Analysis and Implementation

ID: LL-302
Date: 2026-01-23 (Updated: 2026-0...
- **RAG Webhook RAG Query Fix - Irrelevant Lessons Returned** - **Status**: FIXED...


---

## Today's Numbers

| What | Count |
|------|-------|
| Lessons Learned | **5** |
| Critical Issues | 2 |
| High Priority | 1 |
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

5 lessons captured (2 critical, 1 high). Today was a wake-up call. Two critical issues surfaced that could have derailed our entire trading operation. Here's what went wrong and how we're fixing it.

### How do you keep these lessons from getting lost?

We index every lesson into a RAG corpus and query it before new trades and major engineering changes.

### Where is the canonical version of this post?

This post's canonical URL is https://igorganapolsky.github.io/trading/2026/01/23/lessons-learned/.

*Day 87/90 complete. 3 to go.*
