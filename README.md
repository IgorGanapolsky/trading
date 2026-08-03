# trading

Paper-first SPY put-credit lab with deterministic risk gates, broker-reconciled ledgers, and local lessons memory.

> Live trading is blocked. The current put-credit cohort has not proved an edge; tests and healthy automation are not profit evidence.

## Quick start

Requires Python 3.11.

```bash
make setup
make check
make dry-run
```

`make dry-run` performs local health checks and plans a paper strategy action without submitting an order. Broker-backed commands require credentials in environment variables; secrets never belong in the repository.

## Active system

| Concern                                   | Owner                                        |
| ----------------------------------------- | -------------------------------------------- |
| Paper entry, status, and put-credit exits | `scripts/spy_put_credit.py`                  |
| Residual iron-condor exits                | `scripts/residual_ic_manager.py`             |
| Entry and live-trading kill switch        | `src/core/active_strategy.py`                |
| Mandatory risk policy                     | `src/safety/mandatory_trade_gate.py`         |
| Broker order boundary                     | `src/risk/trade_gateway.py`                  |
| Canonical broker/trade ledgers            | `data/system_state.json`, `data/trades.json` |
| Curated operational lessons               | `rag_knowledge/lessons_learned/`             |
| Dependency-free lesson query              | `scripts/query_lessons_learned.py`           |

New `iron_condor` and `ic_simple` entries are killed. The residual manager exists only to reconcile and exit previously opened structures.

## Commands

```bash
make lint       # Ruff checks and formatting verification
make test       # full test suite
make audit      # repository/RAG hygiene audit
make health     # protected-system health snapshot
make check      # lint + audit + tests
make dry-run    # health + paper-only strategy and residual-exit plans
make coverage   # HTML, XML, JSON, and terminal coverage reports
```

## Layout

```text
src/            importable product code
scripts/        explicit operator and maintenance entry points
tests/          unit, integration, contract, and smoke tests
config/         reviewed static configuration
data/           compact canonical ledgers; generated output is ignored
rag_knowledge/  curated sources and lessons, not runtime indexes
docs/           current engineering and operational documentation
.agents/skills/ reusable agent procedure for this repository
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [data/README.md](data/README.md), and [docs/EXTENSIONS.md](docs/EXTENSIONS.md) before changing architecture or operational state.

Multiple agents coordinate through [docs/AGENT_COORDINATION.md](docs/AGENT_COORDINATION.md):
Linear owns the task, the shared Obsidian vault owns the live claim, and the issue-scoped
worktree/PR owns the code change.

## Evidence boundary

- A dry run is a plan, not an order.
- A submitted order is not a fill.
- A paper fill is not live performance.
- A model score or test result is not trading edge.
- Promotion requires the thresholds in `config/strategy_candidate_tournament.json` using broker-paired closed trades.

MIT licensed. Nothing in this repository is financial advice.
