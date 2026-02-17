---
layout: home
title: AI Trading Journey
list_title: " "
---

This is the unfiltered story of building an autonomous AI trading system—every bug, every breakthrough, every lesson learned.

**The goal:** Reach $6K/month after-tax options income as fast as safely possible through disciplined, automated execution.

**Strategy Profile:** Automated iron condor system (SPY-first; expandable to SPX/XSP/QQQ/IWM) with 15-20 delta short strikes, $10-wide wings, and up to 5 concurrent positions.

**Capital Deployment Policy:** Alpaca paper account ($100K) is the primary validation engine. Alpaca brokerage account is traded opportunistically only when the same RAG + risk gates pass.

**The method:** A full autonomous stack where each layer has a strict role:

- **Signal + market data layer**: Alpaca + macro/news inputs feed the orchestrator.
- **Decision layer**: Claude Opus handles trade-critical reasoning; TARS/OpenRouter route non-critical tasks for cost control.
- **Memory layer**: LanceDB RAG retrieves prior failures and lessons before trade and code decisions.
- **Execution layer**: Orchestrator + trade gateway enforce a liquid index-options whitelist (SPY-first; expandable to SPX/XSP/QQQ/IWM), sizing, entry/exit, and stop-loss policies before orders hit Alpaca.
- **Risk layer**: Hard gates (position limits, drawdown controls, pre-trade smoke tests, mandatory checklists) block unsafe actions.
- **Reliability layer**: Ralph Mode and CI workflows continuously test, repair, and document the system.

Full architecture: **[Tech Stack](/trading/tech-stack/)**.

---

## Where We Are Today

<!-- AUTO_STATUS_START -->
_Last Sync: 2026-02-17 20:47 UTC (source: `data/system_state.json`)_

| What | Status |
| ---- | ------ |
| Account Equity | $101,401.96 |
| Daily P/L | -$35.60 |
| Win Rate | 100.0% (1 trades; target 80.0%) |
| Paper Phase | Day 14/90 |
| North Star Gate | ACTIVE (VALIDATING) |
| Open Positions | 0 structure(s), 0 option leg(s) |
| Unrealized P/L | +$0.00 |

**Execution Focus:** Do not scale risk until validation passes.
<!-- AUTO_STATUS_END -->

This section is auto-updated from `data/system_state.json` by `scripts/update_docs_index.py` via GitHub Actions.

---

## Alpaca Account Snapshots (Auto)

<!-- AUTO_SNAPSHOT_START -->
Latest snapshots are refreshed by automation and published to GitHub Pages.

### Paper ($100K) Snapshot + PaperBanana Financial Diagram

| Alpaca Snapshot | PaperBanana Diagram |
| --- | --- |
| ![Alpaca Paper Snapshot](/trading/assets/snapshots/alpaca_paper_latest.png) | ![PaperBanana Paper Diagram](/trading/assets/snapshots/paperbanana_paper_latest.svg) |

Captured: `2026-02-17T20:16:23Z`

Technical readout: Paper Account: net liquidation value $101,382.04; daily P/L -55.52 (+0.0 bps) indicating a negative drift session; cumulative P/L +1,382.04 (+1.38%); low capital deployment at 0.8% utilization with cash $100,542.04; open position proxy 2; win-rate estimate 100.0% (n=1); North Star gate MEDIUM.

### Brokerage (Live) Snapshot + PaperBanana Financial Diagram

| Alpaca Snapshot | PaperBanana Diagram |
| --- | --- |
| ![Alpaca Brokerage Snapshot](/trading/assets/snapshots/alpaca_live_latest.png) | ![PaperBanana Brokerage Diagram](/trading/assets/snapshots/paperbanana_live_latest.svg) |

Captured: `2026-02-17T20:16:23Z`

Technical readout: Brokerage Account: net liquidation value $207.90; daily P/L +0.00 (+0.0 bps) indicating a flat premium-decay session; cumulative P/L +187.90 (+939.50%); high capital deployment at 90.4% utilization with cash $40.00; open position proxy 0; win-rate estimate 0.0% (n=0); North Star gate MEDIUM.

### Progress Dashboard Snapshot
![Progress Dashboard Snapshot](/trading/assets/snapshots/progress_latest.png)

Captured: `2026-02-17T20:16:23Z`

Manifest: [`/trading/data/alpaca_snapshots.json`](/trading/data/alpaca_snapshots.json)
<!-- AUTO_SNAPSHOT_END -->

---

## Featured Posts

- **[The Silent 74 Days](/trading/2026/01/07/the-silent-74-days/)** — How we built a system that did nothing for 74 days
- **[Complete Iron Condor Guide](/trading/2026/01/21/iron-condors-ai-trading-complete-guide/)** — Our full strategy and tech stack
- **[The Position Stacking Disaster](/trading/2026/01/22/position-stacking-disaster-fix/)** — A bug that cost $1,472 in paper trading

[View all posts by category →](/trading/blog/)

---

_Built by Igor Ganapolsky (CEO) with Claude-powered autonomous agents, including Ralph Mode._
