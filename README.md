# trading

**paper-first SPY options validation lab** with broker-backed ledgers, hard risk gates, and agent-bypass-proof safety.

[docs](docs/README.md) · [operator guide](docs/operator-guide.md) · [agent skill](skills/trading-ops/SKILL.md) · [live strategy](docs/LIVE_STRATEGY.md)

---

**guardrails first. edge second.**

- **trade gateway** — every new-risk path hits `TradeGateway` before the broker
- **kill switch** — strategy family is explicit in `data/runtime/strategy_kill_switch.json`
- **paired ledger** — closed outcomes in `data/trades.json`; unmatched fills stay quarantined
- **RAG memory** — lessons under `rag_knowledge/lessons_learned/` feed gates and ops
- **paper only for active validation** — live capital blocked until cohort criteria clear

Active family: **`spy_put_credit`** (1-lot SPY bull put credit, paper). Iron condor **new entries are killed**; residual IC legs are exit-only.

This is **not** a proven profitable system. Current edge is unproven until the put-credit cohort hits n≥30 with expectancy > 0 and PF > 1. Read ledgers, not marketing.

---

## quick start

```bash
git clone https://github.com/IgorGanapolsky/trading
cd trading
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-minimal.txt   # or: uv sync

# status (no orders)
python scripts/spy_put_credit.py --status
python scripts/audit_open_inventory.py
python scripts/system_health_check.py

# plan only (no submit)
python scripts/spy_put_credit.py --dry-run
```

Credentials: Alpaca paper keys via env / `get_alpaca_credentials()` — never hardcode.

---

## docs

| Path                                                       | Purpose                             |
| ---------------------------------------------------------- | ----------------------------------- |
| [docs/README.md](docs/README.md)                           | docs index                          |
| [docs/operator-guide.md](docs/operator-guide.md)           | human operator runbook              |
| [docs/LIVE_STRATEGY.md](docs/LIVE_STRATEGY.md)             | strategy spec                       |
| [skills/trading-ops/SKILL.md](skills/trading-ops/SKILL.md) | agent skill (operate this repo)     |
| [AGENTS.md](AGENTS.md)                                     | agent instructions for contributors |
| [CONTRIBUTING.md](CONTRIBUTING.md)                         | PR / issue path                     |

---

## current truth (verify on disk)

| Source                                   | Question                            |
| ---------------------------------------- | ----------------------------------- |
| `data/system_state.json`                 | broker equity, positions, last sync |
| `data/trades.json`                       | paired closed-structure outcomes    |
| `data/put_credit_entries.json`           | active put-credit journal           |
| `data/runtime/strategy_kill_switch.json` | active vs killed families           |

Do not invent P/L or win rate. Cite the ledger.

---

## agent instructions

If you are an AI agent working in this repository:

1. Read [`AGENTS.md`](AGENTS.md) before changing code
2. Install/use the operator skill: [`skills/trading-ops/SKILL.md`](skills/trading-ops/SKILL.md)
3. Read [`CONTRIBUTING.md`](CONTRIBUTING.md) before opening PRs

Repo layout ideas (skills, docs hub, clean README pitch) were inspired by
[Herdr](https://github.com/herdrdev/herdr) / [herdr.dev](https://herdr.dev) —
agent skill + plugins docs at [herdr.dev/docs/agent-skill](https://herdr.dev/docs/agent-skill/)
and [herdr.dev/docs/plugins](https://herdr.dev/docs/plugins/). No affiliation.

---

## development

```bash
make check          # ruff (src) + focused pytest if available
make test           # pytest tests/ -q
make hygiene        # worktree prune helper
```

Use a dedicated git worktree for feature work (see AGENTS.md). Never force-push `main`.

---

## license

See [LICENSE](LICENSE).
