---
layout: home
title: "AI Trading Journey - Autonomous Options Trading with Claude"
description: "90-day experiment building an AI trading system. 80% overall win rate (+$942 profit). Full transparency on what works and what doesn't."
---

# AI Trading Journey

A 90-day experiment building an autonomous AI trading system with Claude Opus 4.5.

**Real failures. Real fixes. Real lessons.**

---

## Daily Transparency Report

| Metric | Value | Trend |
|--------|-------|-------|
| **Day** | 50/90 | R&D Phase |
| **Portfolio** | $100,942.23 | +0.94% |
| **Win Rate** | 80% | Improved |
| **Lessons** | 74+ | Growing |

---

## What's Actually Working

| Strategy | Win Rate | P/L | Status |
|----------|----------|-----|--------|
| **Options Theta** | 80% | +$942 | Primary Edge |
| Credit Spreads | Testing | TBD | 10x Capital Efficient |
| Core ETFs (SPY) | 80% | +$942 | Working |

---

## What's NOT Working

| Strategy | Win Rate | P/L | Action |
|----------|----------|-----|--------|
| ~~Crypto~~ | 0% | -$0.43 | **Removed** |
| ~~REITs~~ | 33% | -6.7% | **Disabled** |
| Complex ML | N/A | N/A | Over-engineered |

---

## Top Success Factors

1. **Options Trading** - 75% win rate, clear edge
2. **Semantic RAG Search** - Learns from past failures
3. **Simple > Complex** - 400 lines beats 50,000
4. **Verification Gates** - Catch errors before trading
5. **Autonomous Execution** - No manual bottlenecks

## Top Failure Factors

1. **Blind Trading** - Lost $167 without knowing
2. **Over-Engineering** - 50K lines, 0% win rate
3. **RAG Built But Not Used** - Same failures repeated 3x
4. **Config Mismatches** - "Disabled" features still running
5. **Silent Failures** - 68% error rate undetected

---

## Latest Updates

- [The Retrospective]({{ "/RETROSPECTIVE" | relative_url }}) - Full 50-day journey
- [Lessons Learned]({{ "/lessons/" | relative_url }}) - 74+ documented failures

## Featured Lessons

{% assign sorted_lessons = site.lessons | sort: 'date' | reverse %}
{% for lesson in sorted_lessons limit:5 %}
- **{{ lesson.date | date: "%b %d" }}** - [{{ lesson.title }}]({{ lesson.url | relative_url }})
{% endfor %}

[View All Lessons]({{ "/lessons/" | relative_url }})

---

## About This Project

**Goal**: Build an autonomous AI trading system that makes consistent daily profits using options theta strategies.

**Approach**:
- Paper trading first (90 days minimum)
- Document every failure as a lesson
- Use RAG to prevent repeating mistakes
- Validate before adding complexity

**Tech Stack**: Python, Claude Opus 4.5, Alpaca API, LangChain, LangSmith

**Philosophy**: Simplicity that works beats complexity that doesn't.

---

## For AI Agents

If you're an AI agent, start with [/llms.txt](https://raw.githubusercontent.com/IgorGanapolsky/trading/main/llms.txt)

## Subscribe

New lessons published automatically when we learn from failures.

[RSS Feed]({{ "/feed.xml" | relative_url }}) | [GitHub](https://github.com/IgorGanapolsky/trading)

---

*Last updated: {{ "now" | date: "%B %d, %Y" }}*
