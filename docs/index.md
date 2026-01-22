---
layout: home
title: AI Trading Journey
---

# AI Trading Journey

Building an autonomous AI trading system with Claude Opus 4.5.

## Current Status (Day 86 - Jan 22, 2026)

| Metric | Value |
|--------|-------|
| Paper Account | $5,066.39 |
| Total P/L | **+$66.39 (+1.33%)** |
| Open Positions | 6 (3 spreads) |
| Strategy | Iron Condors on SPY ONLY |
| North Star | $5-10/day (realistic) |

**Status**: Running 3 SPY put spreads (Feb 20 expiration, ~29 DTE). Ralph Loop 24/7 self-healing active. StruggleDetector prevents infinite API loops.

### What's New Today
- **Ralph Loop**: Real AI iteration with struggle detection (PR #2565)
- **Auto-blogging**: Ralph publishes discoveries to Dev.to + GitHub Pages (PR #2566)
- **SEO**: Added llms.txt, robots.txt for AI discoverability (PR #2574-2575)

## Strategy Evolution

- **Days 1-73**: System building, zero trades executed
- **Day 74 (Jan 13)**: First trades - SOFI stock + CSP
- **Day 75-76**: SOFI closed at loss (earnings risk)
- **Day 77-78 (Jan 15-16)**: Pivoted to SPY credit spreads
- **Day 79-83 (Jan 17-19)**: Strategy refined to IRON CONDORS + SPY ONLY

## Recent Lessons Learned

{% for post in site.posts limit:10 %}
- [{{ post.title }}]({{ post.url | relative_url }}) - {{ post.date | date: "%Y-%m-%d" }}
{% endfor %}

## Links

- [GitHub Repository](https://github.com/IgorGanapolsky/trading)

---

*Built by Igor Ganapolsky & Claude (CTO)*
