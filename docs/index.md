---
layout: home
title: AI Trading Journey
---

# AI Trading Journey

Building an autonomous AI trading system with Claude Opus 4.5.

## Current Status (Day 75)

| Metric | Value |
|--------|-------|
| Paper Account | $4,959.26 |
| Total P/L | -$40.74 (-0.81%) |
| Open Positions | 0 (All closed) |
| Strategy | Credit Spreads |
| North Star | $14-25/day (realistic) |

**Jan 14 Update:** Emergency closed SOFI positions before Jan 30 earnings. Accepted -$65.58 daily loss to avoid potential -$800+ earnings risk.

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
