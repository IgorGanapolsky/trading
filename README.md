<div align="center">

# SPY Options Validation System

### Broker-backed validation infrastructure for defined-risk SPY options

**Paper-first. Hard-gated. Measured from paired closed trades, not stories.**

[Public Status](https://igorganapolsky.github.io/trading/) | [Operator Dashboard](https://igorganapolsky.github.io/trading/rag-query/) | [Live Strategy Spec](docs/LIVE_STRATEGY.md) | [Quick Start](#quick-start)

</div>

---

## What This Repository Is

This repository is a trading systems lab focused on one narrow problem:

- validate a repeatable SPY options playbook in paper trading
- enforce risk controls before any order is sent
- track outcomes with broker-backed evidence
- feed lessons back into retrieval and learning workflows

The project target is still the same:

- **North Star**: `$6,000/month` after tax
- **Target capital base**: `$300,000`

But the repo should be understood for what it actually is today:

- **paper-first validation infrastructure**
- **live trading inactive by default**
- **edge not yet verified for scaling**

Current gate state and evidence live in the canonical ledgers and generated public bundle, not in this README:

- [docs/data/public_status.json](/Users/igorganapolsky/workspace/git/igor/trading/.worktrees/gsd-learning-freshness-guard/docs/data/public_status.json)
- [data/system_state.json](/Users/igorganapolsky/workspace/git/igor/trading/.worktrees/gsd-learning-freshness-guard/data/system_state.json)
- [data/trades.json](/Users/igorganapolsky/workspace/git/igor/trading/.worktrees/gsd-learning-freshness-guard/data/trades.json)

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
- **Structure family**: defined-risk options income structures, with iron condors as the primary validated playbook
- **Typical DTE band**: 30-45 days
- **Short strike target**: around 15 delta when the gate path allows it
- **Exit discipline**: profit-taking, stop-loss, and time-based exits enforced through the strategy stack

Whether that playbook is currently allowed to open new risk is determined by the active weekly gate, not by this static document.

The exact active operating spec lives here:

- [docs/LIVE_STRATEGY.md](/Users/igorganapolsky/workspace/git/igor/trading/.worktrees/gsd-learning-freshness-guard/docs/LIVE_STRATEGY.md)

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
