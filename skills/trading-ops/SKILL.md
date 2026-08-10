---
name: trading-ops
description: "Operate the Igor trading lab (paper SPY put-credit validation, broker sync, safety gates, RAG). Use when working in the trading repo, checking status, planning trades, or touching risk/execution code. Prefer dry-run and ledger evidence over claims."
---

# Trading ops (agent skill)

This skill teaches an agent how to **operate** this repository safely. It is not a profit claim.

Repo: paper-first SPY options validation. Active family: **`spy_put_credit`**. Iron condor **new entries killed**.

## Safety gates (hard)

Before any action that could submit orders or close positions:

1. Read `data/runtime/strategy_kill_switch.json` — confirm `active_family` and `live_blocked`.
2. Prefer **paper** paths only. Live is blocked until kill criteria clear.
3. **Do not** freehand-close positions outside `spy_put_credit.py` or `residual_ic_manager.py`.
4. **Do not** remove `data/TRADING_HALTED` / halt flags to “unblock” trading.
5. **Do not** recreate iron-condor entry workflows; they must remain absent.
6. Never hardcode Alpaca keys; use `get_alpaca_credentials()`.

If a tool or hook refuses a boundary action, treat that as signal — find the allowed path or stop.

## Canonical files

| Path                                       | Authority                                      |
| ------------------------------------------ | ---------------------------------------------- |
| `data/system_state.json`                   | Broker snapshot (equity, positions, orders)    |
| `data/trades.json`                         | Paired closed structures (edge metrics)        |
| `data/put_credit_entries.json`             | Put-credit lifecycle journal                   |
| `data/runtime/strategy_kill_switch.json`   | Active / killed strategy families              |
| `src/core/trading_constants.py`            | Policy constants                               |
| `rag_knowledge/lessons_learned/`           | Operator memory                                |
| `rag_knowledge/arxiv/`                     | Continuous arXiv research corpus (Agentic RAG) |
| `data/audit/arxiv_ingestion_manifest.json` | arXiv ingest dedupe + run history              |

Unmatched fills are **not** trades. Do not promote them into win rate / expectancy.

## Continuous arXiv research ingest

Twice-daily GitHub Action (`arxiv-paper-ingestion.yml`) pulls new papers from
[arXiv](https://arxiv.org) (API: `export.arxiv.org`) into `rag_knowledge/arxiv/`
and rebuilds `data/rag/lessons_query.json`. Local:

```bash
make arxiv-ingest
python scripts/arxiv_paper_ingestion.py --query "option credit spread" --json
```

Papers are **research context only** — never treat them as live signals or edge proof.

## Judge panel (claim / PR / coord audit — not trade entry)

Mixture-of-Experts + hard-veto judge for **agent claims**, PR text/diffs, and multi-agent collisions.

```bash
python scripts/judge_panel.py --self-check
python scripts/judge_panel.py --kind claim_audit --text "CI green on run <id> sha <sha>"
python scripts/judge_panel.py --kind pr_audit --diff-file /tmp/patch.diff
python scripts/judge_panel.py --kind coord_audit --agent grok \
  --other-claims-file ~/Documents/AI-Agent-Sync/Agent-State/codex.md \
  --claimed-file src/evals/judge_panel/panel.py
```

- Code: `src/evals/judge_panel/`
- **Never** use this panel to approve put-credit or IC entries (`trade_entry` always vetoes).
- Edge / “ready for live” claims without ledger or run evidence → fail/veto.

## Status commands (read-only first)

```bash
python scripts/spy_put_credit.py --status
python scripts/audit_open_inventory.py
python scripts/system_health_check.py
# optional refresh (mutates local state files; does not open risk by itself)
python scripts/sync_alpaca_state.py
python scripts/sync_closed_positions.py
# Graph RAG (relationships across kill switch, lessons, paired trades)
python scripts/graph_rag_query.py --rebuild
python scripts/graph_rag_query.py --query "why is iron condor killed?" --graph-only
# Hard gate: rebuild + 5 golden multi-hop assertions (CI offline-evals + make check)
python scripts/verify_graph_rag.py
make graph-rag-check
```

Inventory unclean (`exit 2`) → **no new risk**.

## Plan vs execute

```bash
# plan only — no submit
python scripts/spy_put_credit.py --dry-run

# residual IC plan only (not new IC entries)
python scripts/residual_ic_manager.py --dry-run
```

Never describe a dry-run plan as an executed trade.

## Evidence rules

- Equity / P/L / win rate: cite `data/system_state.json` or `data/trades.json` with numbers.
- 0 put-credit closed trades in cohort → no profitability claim.
- Prefer `RETRIEVE → CITE → SPEAK`.

## Git / change protocol

- Feature work in a dedicated `git worktree` under `.worktrees/`.
- PRs for all changes; merge only with green CI evidence.
- No force-push to `main`.
- After substantive ops work, record lessons in `rag_knowledge/lessons_learned/` when severity ≥ 4 or a repeat mistake occurred.

## Tests

```bash
make check
make dry-run
```

## What this skill is not

- Not permission to deploy live capital.
- Not a substitute for broker truth.
- Not a claim that put-credit has edge before n≥30 cohort gates pass.
