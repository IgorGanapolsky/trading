---
layout: home
title: AI Trading Journey
list_title: " "
---

This is the unfiltered story of building an autonomous AI trading system—every bug, every breakthrough, every lesson learned.

**The goal:** $6,000/month passive income through disciplined iron condor trading on SPY.

**The method:** A full autonomous stack where each layer has a strict role:

- **Signal + market data layer**: Alpaca + macro/news inputs feed the orchestrator.
- **Decision layer**: Claude Opus handles trade-critical reasoning; TARS/OpenRouter route non-critical tasks for cost control.
- **Memory layer**: LanceDB RAG retrieves prior failures and lessons before trade and code decisions.
- **Execution layer**: Orchestrator + trade gateway enforce SPY-only, sizing, entry/exit, and stop-loss policies before orders hit Alpaca.
- **Risk layer**: Hard gates (position limits, drawdown controls, pre-trade smoke tests, mandatory checklists) block unsafe actions.
- **Reliability layer**: Ralph Mode and CI workflows continuously test, repair, and document the system.

Full architecture: **[Tech Stack](/trading/tech-stack/)**.

---

## Where We Are Today

<!-- AUTO_STATUS_START -->
_Last Sync: 2026-02-16 16:45 UTC (source: `data/system_state.json`)_

| What | Status |
| ---- | ------ |
| Account Equity | $101,441.56 |
| Daily P/L | +$0.00 |
| Win Rate | 100.0% (1 trades; target 80.0%) |
| Paper Phase | Day 14/90 |
| North Star Gate | ACTIVE (VALIDATING) |
| Open Positions | 1 structure(s), 4 option leg(s) |
| Unrealized P/L | +$2.00 |

**Execution Focus:** Do not scale risk until validation passes.
<!-- AUTO_STATUS_END -->

This section is auto-updated from `data/system_state.json` by `scripts/update_docs_index.py` via GitHub Actions.

---

## Featured Posts

- **[The Silent 74 Days](/trading/2026/01/07/the-silent-74-days/)** — How we built a system that did nothing for 74 days
- **[Complete Iron Condor Guide](/trading/2026/01/21/iron-condors-ai-trading-complete-guide/)** — Our full strategy and tech stack
- **[The Position Stacking Disaster](/trading/2026/01/22/position-stacking-disaster-fix/)** — A bug that cost $1,472 in paper trading

[View all posts by category →](/trading/blog/)

---

_Built by Igor Ganapolsky (CEO) with Claude-powered autonomous agents, including Ralph Mode._
