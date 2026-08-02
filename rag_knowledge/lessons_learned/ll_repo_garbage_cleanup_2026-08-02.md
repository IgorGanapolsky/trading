# LL-338: Repo Garbage Cleanup (2026-08-02)

## Problem

Git tracked ~1,100+ runtime/agent artifacts that do not belong in source control:

- `data/screenshots/` (~240MB PNGs)
- `data/audit/`, `data/agent_context/`, analysis/report dumps
- `logs/autonomous_trading_*.json`, `artifacts/**`, `.playwright-mcp/`
- Deprecated `data/trades_YYYY-MM-DD.json` dumps
- Displaced `docs/contest/` duplicate of `contest/`

## Fix

1. `git rm --cached` on garbage prefixes (files remain local where needed).
2. Expand `.gitignore` with `REPO HYGIENE (2026-08-02)` block.
3. Keep canonical ledgers: `system_state.json`, `trades.json`, `put_credit_entries.json`,
   `strategy_params.json`, `runtime/strategy_kill_switch.json`.
4. Prevention: `tests/test_repo_hygiene.py` fails if forbidden paths re-enter the index.

## Rule

Never commit screenshots, audit dumps, agent context memories, or daily raw trade dumps.
Paired outcomes live only in `data/trades.json`.

## Tags

#hygiene #gitignore #repo-cleanup #prevention
