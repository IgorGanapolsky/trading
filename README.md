# trading

**Paper-first SPY options validation lab** with broker-backed ledgers, deterministic risk gates, and local lessons memory.

[Docs](docs/README.md) · [Operator guide](docs/operator-guide.md) · [Agent skill](skills/trading-ops/SKILL.md) · [Coordination](docs/AGENT_COORDINATION.md)

> Live trading is blocked. The active put-credit edge is not proven; tests, healthy automation, plans, and paper fills are not profit evidence.

## Guardrails first, edge second

- **Trade gateway** — new-risk paths cross `TradeGateway` before the broker.
- **Kill switch** — active and killed strategy families are explicit in `data/runtime/strategy_kill_switch.json`.
- **Paired ledger** — closed outcomes live in `data/trades.json`; unmatched fills remain quarantined.
- **RAG memory** — curated lessons under `rag_knowledge/lessons_learned/` inform operations and gates.
- **Paper validation** — live capital stays blocked until the reviewed cohort criteria pass.

Active family: **`spy_put_credit`** (1-lot SPY bull put credit, paper). New iron-condor entries are killed; existing residual IC legs are exit-only.

## Quick start

Requires Python 3.11.

```bash
git clone https://github.com/IgorGanapolsky/trading
cd trading
make setup

# Read-only status and local health
.venv/bin/python scripts/spy_put_credit.py --status
.venv/bin/python scripts/audit_open_inventory.py
make health

# Plans only; no order submission
make dry-run
```

Broker-backed commands read paper credentials from environment variables or the local credential helper. Never hardcode credentials.

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

## Commands

```bash
make lint        # Ruff checks and formatting verification
make test        # full Python test suite
make coverage    # branch coverage in terminal, XML, JSON, and HTML
make audit       # repository and RAG hygiene audit
make security    # dependency and high-confidence static-security checks
make health      # bounded protected-system health snapshot
make check       # lint + audit + security + contracts + full tests
make dry-run     # health + paper-only strategy and residual-exit plans
```

## Repository map

| Path             | Purpose                                                |
| ---------------- | ------------------------------------------------------ |
| `src/`           | Importable product code                                |
| `scripts/`       | Explicit operator and maintenance entry points         |
| `tests/`         | Unit, integration, contract, and smoke tests           |
| `skills/`        | Reusable agent procedures                              |
| `config/`        | Reviewed static configuration                          |
| `data/`          | Compact canonical ledgers; generated output is ignored |
| `rag_knowledge/` | Curated sources and lessons, not runtime indexes       |
| `docs/`          | Current engineering and operating documentation        |

Start with [CONTRIBUTING.md](CONTRIBUTING.md), [data/README.md](data/README.md), and [docs/EXTENSIONS.md](docs/EXTENSIONS.md).

## Multi-agent coordination

[docs/AGENT_COORDINATION.md](docs/AGENT_COORDINATION.md) defines the layered contract:

- **Herdr**: live pane and agent lifecycle.
- **Linear**: durable task ownership.
- **Shared Obsidian vault**: live claim and handoff record.
- **Issue-scoped worktree and PR**: authoritative code change and review.

The Obsidian Linear plugin is a human dashboard, not a lock. Repository organization and first-class skill ideas are inspired by [Herdr](https://github.com/herdrdev/herdr), its [agent-skill guide](https://herdr.dev/docs/agent-skill/), and its [plugin guide](https://herdr.dev/docs/plugins/); there is no affiliation.

## Evidence boundary

- A dry run is a plan, not an order.
- A submitted order is not a fill.
- A paper fill is not live performance.
- A model score or test result is not trading edge.
- Promotion requires reviewed thresholds backed by broker-paired closed trades.

MIT licensed. Nothing in this repository is financial advice.
