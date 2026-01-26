---
layout: home
title: Ralph Mode - Building an AI Trading System in Public
---

# Building an AI Trading System in Public

This is the unfiltered story of building an autonomous AI trading system—every bug, every breakthrough, every lesson learned.

**The goal:** $6,000/month passive income through disciplined iron condor trading on SPY.

**The method:** Claude Opus 4.5 as CTO, running 24/7 autonomous operations using the [Ralph Wiggum iterative coding technique](https://github.com/Th0rgal/opencode-ralph-wiggum).

---

## Where We Are Today (Day 88)

| Metric | Value |
|--------|-------|
| Paper Account | $29,991.36 |
| Strategy | Iron Condors on SPY |
| Open Positions | 0 |
| Status | Weekend - Markets Closed |

**What's happening:** Fresh start with $30K. Validating our iron condor strategy in paper trading before scaling. Ralph Mode runs 24/7, automatically fixing issues and publishing what it learns.

---

## The Story So Far

### The Silent 74 Days (Nov 1 - Jan 12)
For 74 days, our system showed green dashboards while executing zero trades. [Read the full post-mortem](/trading/2026/01/07/the-silent-74-days.html)—it's one of those engineering failures you learn from.

### First Trades (Jan 13)
We finally executed trades. Bought SOFI. Learned why individual stocks are riskier than index ETFs.

### Strategy Pivot (Jan 15-19)
After getting burned on SOFI, we pivoted to SPY-only iron condors. The math:
- Individual stocks: Unpredictable, earnings risk, wide spreads
- SPY iron condors: 86% win rate, defined risk, best liquidity

### Ralph Mode Activated (Jan 22)
The system now heals itself. CI workflows detect issues, apply fixes, and document discoveries automatically. [See today's discoveries](/trading/2026/01/24/ralph-discovery.html).

### Fresh Start (Jan 22)
Reset to $30K. Clean slate. No PDT restrictions. Now we prove the strategy works.

---

## Featured Posts

### Must-Read
- **[The Silent 74 Days](/trading/2026/01/07/the-silent-74-days.html)** - How we built a system that did nothing
- **[Complete Iron Condor Guide](/trading/2026/01/21/iron-condors-ai-trading-complete-guide.html)** - Our full strategy and tech stack
- **[The Position Stacking Disaster](/trading/2026/01/22/position-stacking-disaster-fix.html)** - A bug that cost $1,472 in paper trading

### Recent Updates
{% for post in site.posts limit:5 %}
- [{{ post.title }}]({{ post.url | relative_url }}) <small>({{ post.date | date: "%b %d" }})</small>
{% endfor %}

[View all posts →](/trading/posts/)

---

## Follow the Journey

- **[GitHub Repository](https://github.com/IgorGanapolsky/trading)** - Full source code, issues, and PRs
- **[GitHub Actions](https://github.com/IgorGanapolsky/trading/actions)** - Watch Ralph work in real-time

Every trade gets recorded. Every bug gets documented. Every lesson goes into our [RAG knowledge base](https://github.com/IgorGanapolsky/trading/tree/main/rag_knowledge/lessons_learned).

---

*Built by Igor Ganapolsky (CEO) & Ralph (AI CTO) - Powered by Claude Opus 4.5*
