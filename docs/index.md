---
layout: home
title: AI Trading Journey
---

Building an autonomous AI trading system with Claude Opus 4.5.

## Current Status (Day 83 - Jan 19, 2026)

| Metric | Value |
|--------|-------|
| Paper Account | $4,986.39 |
| Total P/L | **-$13.61 (-0.27%)** |
| Open Positions | 6 (3 SPY put spreads) |
| Strategy | Iron condors on SPY |
| North Star | $5-10/day (realistic) |

**Status**: Market closed (MLK Day). Reviewing positions for Tuesday open.

## Strategy Evolution

- **Days 1-73**: System building, zero trades executed
- **Day 74 (Jan 13)**: First trades - SOFI stock + CSP
- **Day 75-76**: SOFI closed at loss (earnings risk)
- **Day 77-78 (Jan 15-16)**: Pivoted to SPY credit spreads
- **Day 79-83 (Jan 17-19)**: Transitioned to iron condors per backtest data

## Blog Posts

{% for post in site.posts limit:10 %}
- [{{ post.title }}]({{ post.url | relative_url }}) - {{ post.date | date: "%Y-%m-%d" }}
{% endfor %}

## Links

- [GitHub Repository](https://github.com/IgorGanapolsky/trading)
- [Lessons Learned]({{ "/lessons" | relative_url }}) (in RAG only)

---

*Built by Igor Ganapolsky & Claude*
