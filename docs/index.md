---
layout: home
title: "AI Trading Journey - Autonomous Options Trading with Claude"
description: "90-day experiment building an AI trading system. Fresh start with real brokerage. Full transparency on what works and what doesn't."
---

# AI Trading Journey

A 90-day experiment building an autonomous AI trading system with Claude Opus 4.5.

**Real failures. Real fixes. Real lessons.**

---

## Daily Transparency Report

### Real Brokerage (LIVE)

| Metric | Value | Trend |
|--------|-------|-------|
| **Started** | Jan 3, 2026 | Day 1 |
| **Cash** | $20.00 | Fresh Start |
| **Positions** | 0 | Building |
| **Daily Deposit** | $10/day | Accumulating |
| **Target** | $100/day profit | North Star |

### Current Positions (Live Account)

| Symbol | Type | Entry | Current | P/L |
|--------|------|-------|---------|-----|
| *None yet* | - | - | - | - |

> **Status**: Accumulating capital. First options trade when we reach minimum for defined-risk spreads (~$100-200).

### Paper Trading (R&D)

| Metric | Value | Trend |
|--------|-------|-------|
| **Day** | 50/90 | R&D Phase |
| **Portfolio** | $100,942.23 | +0.94% |
| **Win Rate** | 80% | Proven |
| **Lessons** | 75+ | Growing |

#### Open Positions (0)

| Symbol | Type | Entry | Current | P/L |
|--------|------|-------|---------|-----|
| *No open positions* | - | - | - | - |

> **Total Position Value**: $0.00 | **Unrealized P/L**: +$0.00

> **Strategy**: Backtest and analyze during off-hours. Apply proven strategies to real account.

[View Full Dashboard]({{ "/progress_dashboard" | relative_url }})

---

## What's Working

| Strategy | Win Rate | Status |
|----------|----------|--------|
| **Options Theta** | 80% | Primary Edge |
| **Core ETFs (SPY)** | 80% | Active |
| Credit Spreads | Testing | 10x Capital Efficient |

---

## Key Success Factors

1. **Options Trading** - 80% win rate, clear edge
2. **Simplicity** - 400 lines beats 50,000
3. **RAG Learning** - Don't repeat mistakes
4. **Verification Gates** - Catch errors before trading

---

## Latest Updates

- [The Retrospective]({{ "/RETROSPECTIVE" | relative_url }}) - Full 50-day journey
- [Lessons Learned]({{ "/lessons/" | relative_url }}) - 75+ documented failures

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
