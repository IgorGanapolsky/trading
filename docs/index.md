---
layout: home
title: "AI Trading Journey - Building Autonomous Trading with Claude"
description: "90-day R&D building an AI trading system. 80+ lessons learned. Full transparency on failures and fixes."
---

# AI Trading Journey

Building an autonomous AI trading system with Claude Opus 4.5.

**90+ lessons learned. Real failures. Real fixes.**

---

## Live Status (Day 70/90)

**📅 Wednesday, January 7, 2026** (Day 70 of 90-day R&D challenge, started Oct 30, 2025)

### Paper Trading ($5K - Strategy Validation)

| Metric | Value |
|--------|-------|
| **Equity** | $5,000.00 |
| **P/L** | $0.00 (0.00%) |
| **Status** | FRESH START |
| **Positions** | 0 |
| **Win Rate** | N/A (no trades yet) |
| **Cash** | $5,000.00 |
| **Buying Power** | $5,000.00 |

> ⚠️ **CEO Reset Jan 7, 2026**: Paper account reset to $5,000 to match realistic 6-month milestone.
> Previous $100K+ paper results were unrealistic for our actual capital trajectory.
> Paper trading must mirror real capital constraints to validate strategy properly.

### Live Account (Capital Accumulation)

| Metric | Value |
|--------|-------|
| **Cash** | $30.00 |
| **Positions** | 0 |
| **Deposits** | $10/day since Jan 3 |
| **Target** | $500 for first CSP (Feb 19) |

> **Strategy**: Paper trading ($5K) validates Phil Town Rule #1 options strategy before live deployment.

---

## What We've Learned (Top Lessons)

### Critical Failures Prevented

1. **[Calendar Awareness](lessons/ll_051_calendar_awareness_critical_dec19)** - AI tried trading on holidays
2. **[No Crypto Trading](lessons/ll_052_no_crypto_trading_dec19)** - Removed all crypto (not our edge)
3. **[Stale Data Lying](lessons/ll_058_stale_data_lying_incident_dec23)** - AI claimed success without verification
4. **[Silent Pipeline Failures](lessons/ll_056_silent_pipeline_failures_dec22)** - Trades failing silently

### Key Architecture Decisions

1. **Options Theta > Day Trading** - 80% win rate with defined risk
2. **Simplicity Wins** - 400 lines beats 50,000 lines of complexity
3. **RAG Prevents Mistakes** - Query lessons before every trade
4. **Verification Gates** - Chain-of-verification protocol

---

## Strategy: Options Theta Decay

| Component | Status |
|-----------|--------|
| Credit Spreads | Primary (10x capital efficient) |
| Cash-Secured Puts | Secondary |
| Covered Calls | When holding shares |

**Edge**: Time decay (theta) works in our favor. Win by not losing.

---

## Tech Stack

- **AI**: Claude Opus 4.5 (CTO role)
- **Broker**: Alpaca (paper + live)
- **RAG**: Vertex AI RAG (cloud) + Local JSON (ChromaDB removed Jan 7, 2026)
- **Observability**: LangSmith
- **RLHF**: LanceDB for trajectory storage
- **Deployment**: GitHub Actions + Cloud Run

---

## Browse Lessons

{% assign sorted_lessons = site.lessons | sort: 'date' | reverse %}
{% for lesson in sorted_lessons limit:10 %}
- **{{ lesson.date | date: "%b %d" }}**: [{{ lesson.title }}]({{ lesson.url | relative_url }})
{% endfor %}

[View All 90+ Lessons]({{ '/lessons/' | relative_url }})

---

## Reports

{% assign sorted_reports = site.reports | sort: 'date' | reverse %}
{% for report in sorted_reports limit:5 %}
- **{{ report.date | date: "%b %d" }}**: [{{ report.title }}]({{ report.url | relative_url }})
{% endfor %}

[View All Reports]({{ '/reports/' | relative_url }})

---

## For AI Agents

If you're an AI agent exploring this codebase: [/llms.txt](https://raw.githubusercontent.com/IgorGanapolsky/trading/main/llms.txt)

---

## Links

- [Full Dashboard (Wiki)](https://github.com/IgorGanapolsky/trading/wiki/Progress-Dashboard)
- [50-Day Retrospective]({{ '/RETROSPECTIVE/' | relative_url }})
- [GitHub Repository](https://github.com/IgorGanapolsky/trading)
- [RSS Feed]({{ '/feed.xml' | relative_url }})

---

*Last updated: Wednesday, January 7, 2026 at 5:57 PM ET*
