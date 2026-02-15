---
layout: "post"
title: "Day 95: What We Learned - January 31, 2026"
description: "Markets are closed, but the learning never stops. While other traders take the weekend off, we're refining our edge."
date: "2026-01-31"
last_modified_at: "2026-01-31"
image: "/assets/og-image.png"
tags:
  - "lessons-learned"
  - "ai-trading"
  - "rag"
  - "building-in-public"
day_number: 95
lessons_count: 3
critical_count: 0
excerpt: "Markets are closed, but the learning never stops. While other traders take the weekend off, we're refining our edge."
faq: true
questions:
  - question: "What did we learn on Day 95?"
    answer: "3 lessons captured (0 critical, 3 high). Markets are closed, but the learning never stops. While other traders take the weekend off, we're refining our edge."
  - question: "How does this system remember lessons learned?"
    answer: "We store each lesson in a RAG index and retrieve similar past incidents before future trades and engineering changes."
  - question: "Where can I browse the full code and history?"
    answer: "The full repository and daily updates are published publicly on GitHub and GitHub Pages."
---
# Day 95 of 90 | Saturday, January 31, 2026

**0 days remaining** in our journey to build a profitable AI trading system.

Markets are closed, but the learning never stops. While other traders take the weekend off, we're refining our edge.

---

## Important Discoveries

*Not emergencies, but insights that will shape how we trade going forward.*

### Iron Condor Management - 71,417 Trade Study

Analysis of 71,417 iron condor trades on SPY (2007-2017) reveals optimal management strategies.

### VIX-Based Iron Condor Entry Rules

Research-backed entry rules for iron condors based on VIX levels and IV rank.

### XSP vs SPY - Section 1256 Tax Optimization

XSP (Mini-SPX) options qualify for Section 1256 tax treatment (60/40), potentially saving 25%+ on taxes vs SPY options.


---

## Today's Numbers

| What | Count |
|------|-------|
| Lessons Learned | **3** |
| Critical Issues | 0 |
| High Priority | 3 |
| Improvements | 0 |

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

3 lessons captured (0 critical, 3 high). Markets are closed, but the learning never stops. While other traders take the weekend off, we're refining our edge.

### How do you keep these lessons from getting lost?

We index every lesson into a RAG corpus and query it before new trades and major engineering changes.

### Where is the canonical version of this post?

This post's canonical URL is https://igorganapolsky.github.io/trading/2026/01/31/lessons-learned/.

*Day 95/90 complete. 0 to go.*
