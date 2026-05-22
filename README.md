<div align="center">

# Systematic SPY Options Alpha: RAG-Governed Algotrading Lab

### Paper-First Validation | RAG-ML Safety Governance | Broker-Backed Evidence

**Transforming discretionary options trading into a disciplined, data-driven, and autonomous asset.**

[Public Status](https://igorganapolsky.github.io/trading/) | [Investor Pitch](docs/INVESTOR_PITCH.md) | [Operator Dashboard](https://igorganapolsky.github.io/trading/rag-query/) | [Live Strategy Spec](docs/LIVE_STRATEGY.md)

</div>

---

## 🚀 The Thesis: Prove an Edge Before Claiming One

Most algorithmic trading systems fail because they trade a backtested pattern that was never real. This lab is built to avoid that failure mode: no edge is claimed until a fresh, pre-registered sample proves it.

A quantitative audit of the first 69 paired trades ([docs/research/2026-05-19-edge-analysis.md](docs/research/2026-05-19-edge-analysis.md)) found **no statistically robust edge** — cohort win rate 23.2%, profit factor 0.22, realized **−$3,958**. A "60% win rate on Thursdays" slice looked promising but **failed multiple-comparison correction** (Bonferroni adj_p = 0.190 across K=39 buckets) and its point estimate sits below the strategy's own break-even win rate. The repo treats that as a hypothesis to disprove, not an edge to sell.

## 👥 Who This Is For — and the Open-Core Model

This repo is for developers and quant-minded operators building or running their
own **autonomous trading agents** who want governance and validation discipline
rather than hype — "how do I stop my own agent from placing a stupid trade, and
how do I know whether the strategy actually has an edge?"

**Open core — free, MIT, everything in this repository today:**

- the mandatory risk gateway and deterministic hard risk gates
- paired-trade accounting that separates raw fills from real closed-trade P/L
- the kill-criteria + controlled-experiment validation methodology
- broker-backed daily scorecards, including the honest (currently negative) ledger

**Planned paid layer — not built yet, do not expect it today:**

- a hosted/managed tier of the governance + validation tooling
- if and when the 30-trade validation completes with a proven edge, the audited
  track record becomes a separate, higher-value offering

There is **no paid product and no revenue yet** — the paid layer is contingent on
the validation. The dual-track plan is in
[`.claude/rules/cto-decision-2026-05-21-go-to-market.md`](.claude/rules/cto-decision-2026-05-21-go-to-market.md).

**Build-in-public:** the scorecard is public and currently shows a loss. That
transparency is the point — it is the difference between this and a marketing bot.

## 🧠 Design: RAG-Governed Machine Learning

We solve the "Black Box" problem of ML through a unique **RAG-to-ML Feedback Loop**:

- **Semantic RAG (LanceDB)**: 249 historical lessons act as a real-time safety "governor."
- **GRPO Policy Optimization**: Our ML model is penalized during training for violating documented RAG lessons.
- **Deterministic Hard-Gating**: 7-DTE exit mandates and 14-DTE entry buffers are enforced at the code level to eliminate gamma risk.

## 📊 Performance & Operational Truth

This is not a "get rich quick" bot. It is a **validation infrastructure** that prioritizes broker-backed proof over marketing claims:

- **North Star**: Target `$6,000/month` yield on a `$300,000` capital base — a target, not a result.
- **Safety governor**: pre-trade gates plus RAG lessons block known-bad setups before they reach the broker; live approval/blocked counts are in the generated status bundle, not in this README.
- **Verification**: Fully auditable via Alpaca broker syncs and daily scorecards.

But the repo should be understood for what it actually is today:

- **paper-first validation infrastructure**
- **live trading inactive by default**
- **edge not yet verified for scaling**

Current gate state and evidence live in the canonical ledgers and generated public bundle, not in this README:

- [docs/data/public_status.json](docs/data/public_status.json)
- [data/system_state.json](data/system_state.json)
- [data/trades.json](data/trades.json)

---

## Current Operating Truth

The system is not positioned as a finished black-box profit engine.

It is currently:

- validating a defined-risk SPY options process in paper
- using weekly gates to block scale until there is enough paired closed-trade evidence
- using a broker-backed scorecard to separate realized activity, open-position repricing, and paired closed-trade outcomes

It is not currently:

- a fully validated live strategy
- a claim of proven profitability
- a hands-off capital allocator that should be trusted without supervision

If you want the latest numbers, use the live artifacts and dashboards, not hardcoded README badges.

---

## System Design

The core architecture is built around five layers:

1. **Execution and Brokerage**
   - Alpaca is the primary broker and execution source of truth.
   - Daily scorecards read broker state directly.

2. **Trade Safety**
   - Pre-trade gates enforce ticker restrictions, volatility/risk conditions, and weekly operating constraints.
   - Defined-risk structures only.

3. **Paired-Trade Accounting**
   - The system distinguishes fill flow from completed paired closed trades.
   - Expectancy and scale decisions are supposed to come from paired outcomes, not raw order noise.

4. **RAG and Learning**
   - Lessons learned are stored and retrieved for operator context.
   - Always-on workflows refresh ingest, retraining, and proof artifacts.

5. **Operational Proof**
   - GitHub Actions, smoke checks, workflow validation, and broker-backed artifacts provide evidence for system state.

---

## Active Strategy Scope

The active scope is intentionally narrow:

- **Underlying**: SPY
- **Structure family**: defined-risk options income structures, with iron condors as the primary playbook under validation
- **Typical DTE band**: 30-45 days
- **Short strike target**: around 15 delta when the gate path allows it
- **Exit discipline**: profit-taking, stop-loss, and time-based exits enforced through the strategy stack

Whether that playbook is currently allowed to open new risk is determined by the active weekly gate, not by this static document.

The exact active operating spec lives here:

- [docs/LIVE_STRATEGY.md](docs/LIVE_STRATEGY.md)

---

## Tech Stack

- **Python 3.11**
- **Alpaca** for brokerage, orders, account state, and paper/live parity
- **GitHub Actions** for CI, hygiene, and scheduled automation
- **LanceDB/local retrieval** for lessons and RAG access
- **Structured JSON ledgers** for canonical state and paired-trade evidence
- **Optional market/research providers** behind guarded interfaces, not hard dependencies in the critical trading path

---

## Quick Start

```bash
git clone https://github.com/IgorGanapolsky/trading.git
cd trading
pip install -r requirements.txt
cp .env.example .env
python scripts/system_health_check.py
python scripts/daily_scorecard.py --repo-root .
```

Useful entry points:

- `python scripts/system_health_check.py`
- `python scripts/daily_scorecard.py --repo-root .`
- `python scripts/always_on_learning_loop.py --phase morning_proof --repo-root .`

---

## What Makes This Repo Valuable

The value is not “AI that trades for you.”

The value is that it tries to turn discretionary options trading into something:

- auditable
- broker-backed
- risk-gated
- regression-tested
- measurable from completed trade evidence

That is a more serious asset than a marketing bot with a P/L claim.

---

## What Still Needs Work

This repository still has real gaps:

- overall test coverage is improving but not complete
- some large orchestration surfaces still need deeper verification
- the trading process still needs cleaner cadence and cleaner paired closed-trade evidence
- documentation must continue to stay aligned with actual gate state and actual broker-backed results

This README is intentionally conservative. It is better to under-claim than to advertise a capability the ledgers do not support.

---

## License

[MIT](LICENSE)
