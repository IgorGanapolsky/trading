---
layout: home
title: AI Trading Journey
---

# AI Trading Journey

Building an autonomous AI trading system with Claude Opus 4.5.

## Current Status (Day 85 - Jan 21, 2026)

| Metric | Value |
|--------|-------|
| Paper Account | $5,066.39 |
| Total P/L | **-$86 (unrealized)** |
| Open Positions | 2 (SOFI put + SPY shares) |
| Strategy | Iron Condors on SPY ONLY |
| North Star | $5-10/day (realistic) |

**Status**: Markets closed (MLK Day was Jan 20). SOFI position violates SPY-ONLY mandate - auto-close workflow scheduled for 9:35 AM ET Jan 22. Multiple fixes deployed today: LL-279 (partial iron condor auto-close), LL-280 (position limit counting), LL-281 (CALL pricing fallbacks).

## Strategy Evolution

- **Days 1-73**: System building, zero trades executed
- **Day 74 (Jan 13)**: First trades - SOFI stock + CSP
- **Day 75-76**: SOFI closed at loss (earnings risk)
- **Day 77-78 (Jan 15-16)**: Pivoted to SPY credit spreads
- **Day 79-83 (Jan 17-19)**: Strategy refined to IRON CONDORS + SPY ONLY
- **Day 84 (Jan 20)**: MLK Day - Markets closed
- **Day 85 (Jan 21)**: Fixed 3 critical bugs (LL-279, LL-280, LL-281). Added SEO + blog auto-publish

## Recent Lessons Learned

{% for post in site.posts limit:10 %}
- [{{ post.title }}]({{ post.url | relative_url }}) - {{ post.date | date: "%Y-%m-%d" }}
{% endfor %}

## Links

- [GitHub Repository](https://github.com/IgorGanapolsky/trading)

---

*Built by Igor Ganapolsky & Claude (CTO)*
