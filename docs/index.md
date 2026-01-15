---
layout: home
title: AI Trading Journey
---

# AI Trading Journey

Building an autonomous AI trading system with Claude Opus 4.5.

## Current Status (Day 77 - Jan 15, 2026)

| Metric | Value |
|--------|-------|
| Paper Account | $4,989.69 |
| Total P/L | **-$10.31 (-0.21%)** |
| Today's P/L | +$30.51 |
| Open Positions | 6 |
| Strategy | Credit Spreads on SPY |
| North Star | $150-200/month (3-4%) |

**Status**: SPY credit spreads active. Orphan SPY 660P gained +$36 today. Recovery in progress.

## Strategy Evolution

- **Days 1-73**: System building, zero trades executed
- **Day 74 (Jan 13)**: First trades - SOFI stock + CSP
- **Day 75-76**: SOFI closed at loss (earnings risk)
- **Day 77 (Jan 15)**: SPY credit spreads, +$30.51 unrealized

## Blog Posts

{% for post in site.posts limit:10 %}
- [{{ post.title }}]({{ post.url | relative_url }}) - {{ post.date | date: "%Y-%m-%d" }}
{% endfor %}

## Links

- [GitHub Repository](https://github.com/IgorGanapolsky/trading)
- [Lessons Learned]({{ "/lessons" | relative_url }}) (in RAG only)

---

*Built by Igor Ganapolsky & Claude*
