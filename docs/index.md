---
layout: home
title: AI Trading Journey
---

# AI Trading Journey

Building an autonomous AI trading system with Claude Opus 4.5.

## Current Status (Day 75)

| Metric | Value |
|--------|-------|
| Paper Account | $5,017.76 |
| Total P/L | +$17.76 (+0.36%) |
| Open Positions | 2 (SOFI stock, SOFI put) |
| Strategy | Credit Spreads |
| North Star | $100/day after-tax |

## Strategy Evolution

- **Days 1-73**: System building, zero trades executed
- **Day 74 (Jan 13)**: First trades executed after fixing hardcoded price bug
- **Day 75+**: Credit spread strategy for 10x capital efficiency

## Blog Posts

{% for post in site.posts limit:10 %}
- [{{ post.title }}]({{ post.url | relative_url }}) - {{ post.date | date: "%Y-%m-%d" }}
{% endfor %}

## Links

- [GitHub Repository](https://github.com/IgorGanapolsky/trading)
- [Lessons Learned]({{ "/lessons" | relative_url }}) (in RAG only)

---

*Built by Igor Ganapolsky & Claude*
