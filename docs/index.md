---
layout: home
title: AI Trading Journey
---

# AI Trading Journey

Building an autonomous AI trading system with Claude Opus 4.5.

## Current Status (Day 78 - Jan 16, 2026)

| Metric | Value |
|--------|-------|
| Paper Account | $5,007.98 |
| Total P/L | **+$7.98 (+0.16%)** |
| Today's P/L | +$48.80 |
| Open Positions | 8 |
| Strategy | Credit spreads on SPY |
| North Star | $5-10/day (realistic) |

**Status**: Running SPY credit spreads (Feb 20 expiration). Back in profit territory.

## Strategy Evolution

- **Days 1-73**: System building, zero trades executed
- **Day 74 (Jan 13)**: First trades - SOFI stock + CSP
- **Day 75-76**: SOFI closed at loss (earnings risk)
- **Day 77-78 (Jan 15-16)**: Pivoted to SPY credit spreads - back in profit

## Blog Posts

{% for post in site.posts limit:10 %}
- [{{ post.title }}]({{ post.url | relative_url }}) - {{ post.date | date: "%Y-%m-%d" }}
{% endfor %}

## Links

- [GitHub Repository](https://github.com/IgorGanapolsky/trading)
- [Lessons Learned]({{ "/lessons" | relative_url }}) (in RAG only)

---

*Built by Igor Ganapolsky & Claude*
