# Trading active scope (scrap freeze)

**CEO directive 2026-09-14:** destroy the broken system and start over; make money.

**CTO decision:** this repository is a **paper validation lab**, not a cash business.
Live equity is **$0**. Iron condor new entries are **killed**. Put-credit paired sample
is far below the live gate (`n≥30`, expectancy `>0`, profit factor `>1`).

Linear: [AGENT-615](https://linear.app/igorganapolsky/issue/AGENT-615).

## Allowed (keep)

| Surface                                                                   | Owner                  |
| ------------------------------------------------------------------------- | ---------------------- |
| `scripts/spy_put_credit.py` paper entry / manage-exits / status / dry-run | put-credit validation  |
| `scripts/residual_ic_manager.py` exit-only residual IC                    | inventory cleanup      |
| `scripts/audit_open_inventory.py` + `src/risk/open_inventory_audit.py`    | unclean inventory gate |
| `scripts/sync_alpaca_state.py` / `scripts/sync_closed_positions.py`       | broker truth           |
| `data/trades.json` paired ledger + `data/system_state.json`               | evidence               |
| `data/runtime/strategy_kill_switch.json` with `live_blocked=true`         | strategy lifecycle     |
| `scripts/system_health_check.py` / `make check` / `make dry-run`          | readiness              |
| Narrow adapters behind `src/adapters/`                                    | optional providers     |

## Forbidden until edge + live capital clear

Do **not** merge or recreate:

- New iron-condor / `ic_simple` **entry** workflows or scripts
- “24/7 Ralph / GSD trading execution engine” productization
- “Desk-grade / institutional 10/10” ML+RAG elevation PRs
- Dagster SDA / asset-check engine clones as trading core
- GPT-6 / Astra “next-gen work harness” as a trading dependency
- Pi.dev MCP installs or Pi as a second product control plane
- Live capital deployment / Clear Street migration
- Profit claims or monthly projections before cohort gates pass

## Cash rule

Paper P/L is **not** revenue. Cleared non-owner cash lives outside this repo
(agency / RealEstate / W-2). Agents must route “make money” work to those rails
while this lab stays minimal.

## Prevention

`scripts/audit_active_scope.py` (wired into `make check` via `skill-check`) fails when:

1. `docs/TRADING_ACTIVE_SCOPE.md` is missing
2. kill switch is not `paper_only` + `live_blocked` with active family `spy_put_credit`
3. tracked paths match forbidden theater filename patterns
4. removed IC entry workflows reappear
