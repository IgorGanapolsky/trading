---
layout: home
title: Ralph Mode - AI Trading System
---

# Ralph Mode - AI Trading System

Building an autonomous self-healing AI trading system with Claude Opus 4.5 and the Ralph Wiggum iterative coding technique.

## Current Status (Day 86 - Jan 22, 2026)

| Metric | Value |
|--------|-------|
| Paper Account | $5,066.39 |
| Total P/L | **-$86 (unrealized)** |
| Open Positions | 2 |
| Strategy | Iron Condors on SPY ONLY |
| North Star | $5-10/day (realistic) |
| Ralph Iterations | 39+ autonomous CI runs |

**Status**: Ralph Mode active 24/7. Self-healing CI workflows automatically fix lint errors, merge PRs, and publish discoveries. SOFI position violates SPY-ONLY mandate - auto-close workflow scheduled.

## Strategy Evolution

- **Days 1-73**: System building, zero trades executed
- **Day 74 (Jan 13)**: First trades - SOFI stock + CSP
- **Day 75-76**: SOFI closed at loss (earnings risk)
- **Day 77-78 (Jan 15-16)**: Pivoted to SPY credit spreads
- **Day 79-83 (Jan 17-19)**: Strategy refined to IRON CONDORS + SPY ONLY
- **Day 84 (Jan 20)**: MLK Day - Markets closed
- **Day 85 (Jan 21)**: Fixed 3 critical bugs (LL-279, LL-280, LL-281)
- **Day 86 (Jan 22)**: Ralph Mode activated - 24/7 autonomous self-healing CI

## Recent Lessons Learned

{% for post in site.posts limit:10 %}
- [{{ post.title }}]({{ post.url | relative_url }}) - {{ post.date | date: "%Y-%m-%d" }}
{% endfor %}

## Links

- [GitHub Repository](https://github.com/IgorGanapolsky/trading)

---

*Built by Igor Ganapolsky & Ralph (AI CTO) - Powered by Claude Opus 4.5*
