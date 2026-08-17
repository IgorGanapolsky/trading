# Put-credit research protocol (handbook high-ROI)

Source inspiration: freeCodeCamp Multi-Agent Trading Research System with LangChain Deep Agents (2026-08-14).

## How it helps this lab

- **Agents must not control evidence** → deterministic metrics from `data/trades.json` only.
- **Fixed selection rule before results** → `docs/research/SELECTION_RULE_put_credit.md` + `select_champion()`.
- **Experiment registry** → append-only `data/research/put_credit_protocol/registry.jsonl` (generated; gitignored under `data/research`).
- **Holdout locked until freeze** → chronological tail reserved until one-shot unlock.
- **LangChain / Deep Agents / EODHD** → not adopted (low ROI vs put-credit paper path).
- **Multi-ETF momentum strategies** → out of scope (IC killed; PCS only).

## Commands

```bash
.venv/bin/python scripts/put_credit_research_protocol.py --baseline
.venv/bin/python scripts/put_credit_research_protocol.py --compare-preferred-ivr
.venv/bin/python scripts/put_credit_research_protocol.py --freeze-baseline
.venv/bin/python scripts/put_credit_research_protocol.py --unlock-holdout
.venv/bin/python scripts/put_credit_research_protocol.py --critic-audit
.venv/bin/python scripts/put_credit_cohort_scorecard.py --json  # includes research_protocol
```

## Wired surfaces

- Cohort scorecard schema v2 embeds `research_protocol` + deterministic critic
- `put-credit-validation.yml` runs baseline + critic smoke (no broker)

## Hard boundaries

- Never submits orders.
- Never unblocks live trading.
- Freeze is not EDGE_CANDIDATE; kill criteria on the full cohort still gate live.
