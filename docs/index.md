---
layout: home
title: Building an AI Trading System in Public
---

This is the unfiltered story of building an autonomous AI trading system—every bug, every breakthrough, every lesson learned.

**The goal:** $6,000/month passive income through disciplined iron condor trading on SPY.

**The method:** Claude Opus 4.5 as CTO, running autonomous workflows for trading, risk, and system maintenance. Ralph Mode is one subsystem focused on iterative code repair and self-healing CI.

---

## Where We Are Today

<!-- AUTO_STATUS_START -->
_Last Sync: 2026-02-16 11:15 UTC (source: `data/system_state.json`)_

| What | Status |
| ---- | ------ |
| Account Equity | $101,441.56 |
| Daily P/L | +$0.00 |
| Win Rate | 37.5% (32 trades; target 80.0%) |
| Paper Phase | Day 14/90 |
| North Star Gate | ACTIVE (OFF_TRACK_WIN_RATE) |
| Open Positions | 1 structure(s), 4 option leg(s) |
| Unrealized P/L | +$2.00 |

**Execution Focus:** Do not scale risk until validation passes.
<!-- AUTO_STATUS_END -->

This section is auto-updated from `data/system_state.json` by `scripts/update_docs_index.py` via GitHub Actions.

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

Reset to $30K. Clean slate. No PDT restrictions.

### Scaled to $100K (Jan 30)

Upgraded to $100K paper account for more realistic position sizing. Target: prove 80%+ win rate before live trading.

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
- **[GitHub Actions](https://github.com/IgorGanapolsky/trading/actions)** - Watch autonomous workflows run in real-time
- **[Judge Demo Evidence](/trading/lessons/judge-demo.html)** - Clean, visual summary of proof artifacts and system status

Every trade gets recorded. Every bug gets documented. Every lesson goes into our [RAG knowledge base](/trading/rag-query/) (300+ lessons searchable).

---

_Built by Igor Ganapolsky (CEO) with Claude-powered autonomous agents, including Ralph Mode._
