# Technical Debt Audit — 2026-08-02

## Scope honesty

**Not claimable:** full line-by-line audit of every path and 100% statement coverage
in one session (~1,606 tracked files, ~95k LOC in `src`+`scripts`+`tests`).

This audit is **evidence-based high-ROI debt reduction** with protected-system
checks. A rejected parallel branch (`chore/comprehensive-codebase-audit-20260802`)
deleted `iron-condor-guardian.yml` and mass-deleted workflows — **not merged**.

## Pre-audit baseline (main @ `4f70886bb`)

| Metric | Value |
|--------|-------|
| Tracked files | 1,606 |
| On-disk files (excl. venv/worktrees/git) | ~1,614 |
| Python LOC (`src`+`scripts`+`tests`) | **95,344** |
| Workflows | 82 |
| Scripts (`scripts/*.py`) | 154 |
| `src/**/*.py` | 275 |
| Test modules (`tests/**/*.py`) | ~285 (path count via ls-files) |
| RAG lessons | 319 |
| CI on main | Green (CI + Main Head Verification post-#4324) |
| Inventory audit | clean |
| Active family | `spy_put_credit` paper_only |
| Equity (system_state) | ~$94,150 paper |
| Paired trades | 162 (expectancy −$47.19, PF 0.17; put-credit cohort n=1) |

### Core system snapshot

| System | Status |
|--------|--------|
| Kill switch | `spy_put_credit` active; `ic_simple`/`iron_condor` killed |
| Open inventory | clean (findings=0) |
| RAG readable | 319 lessons loaded |
| Guardian workflow file | present (schedule already disabled; residual exit ownership) |
| CI | green on main before this PR |

### Prior RAG lessons applied

- LL-225: grep before deleting “dead” modules
- LL-repo_garbage_cleanup_2026-08-02: runtime junk already untracked
- boundary-policy: do not remove guardian / kill-switch affordances

## Issues found → fixed

| Issue | Fix |
|-------|-----|
| Zero-ref tactical IC / one-off scripts | Deleted 7 scripts (~500+ LOC) after `git grep` zero-hit verify |
| Misplaced test under `src/strategies/.../__tests__` | Moved to `tests/unit/` |
| `iron-condor-autonomous.yml` still could execute entries via `workflow_dispatch` | Converted to STRATEGY_KILLED refuse no-op |
| `iron-condor-scan.yml` same | Converted to refuse no-op |
| `execute-credit-spread.yml` freehand entry | Converted to refuse no-op |
| `.claude/rules/trading.md` still described IC as active North Star | Rewrote for put-credit + IC killed archive |
| No automated guard against re-enabling killed IC entry workflows | Added `tests/test_killed_ic_workflows.py` |

### Deleted scripts (justification: zero `git grep` refs outside self; not in tests)

1. `scripts/run_spy_tactical_ic.py` — tactical IC runner (strategy killed)
2. `scripts/optimize_win_rate.py` — one-off IC survivability sketch
3. `scripts/validate_thursday_gate.py` — Thursday IC hypothesis toy
4. `scripts/cleanup_old_files.py` — unreferenced local cleaner
5. `scripts/validate_ticker_whitelist.py` — unreferenced
6. `scripts/check_pypi_pins.py` — unreferenced
7. `scripts/perplexity_local_mcp_snapshot.py` — unreferenced snapshot util

## Issues found → not fixed (follow-up)

| Gap | Why deferred |
|-----|----------------|
| Whole-repo 100% test coverage | ~95k LOC; multi-sprint program |
| ~140 scripts still live with sparse tests | Need per-script owner + pre_cleanup_check |
| `src/eval/eval_engineering_skill.py` zero external refs | Research surface; verify before delete |
| `src/analytics/trade_performance.py` zero external refs | May be useful analytics; keep pending import audit |
| Daily perplexity RAG lessons share titles | Date-series, not true duplicates — do not merge blindly |
| Mass workflow deletion | Dangerous (guardian / ops history); neutralize entry paths only |
| `daily-trading.yml` (large) | Needs dedicated read; not mass-deleted this session |
| Parallel audit branch mass-delete | **Rejected** — deleted guardian + 50+ workflows |

## Test coverage

| Item | Status |
|------|--------|
| Full-repo coverage % | **Not remeasured as whole-repo %** (honest gap) |
| New tests this PR | `tests/test_killed_ic_workflows.py` |
| Existing put-credit regime tests | present (`tests/test_put_credit_regime.py`) |
| Hygiene tests | present (`tests/test_repo_hygiene.py`) |

Target “100% operational reliability” remains a **program**, not a one-PR claim.

## CI / prevention

- Killed-workflow refuse patterns + guardian presence enforced by pytest
- Repo hygiene still blocks re-commit of screenshots/logs/audit dumps
- Do not merge any PR that removes `.github/workflows/iron-condor-guardian.yml`

## Recommendation (next sprints)

1. Script inventory with owner matrix (active / residual-exit / archive / delete)
2. `daily-trading.yml` rewrite or retire after put-credit path ownership is explicit
3. Coverage campaign: `trade_gateway`, `spy_put_credit`, residual IC exit only
4. Semantic RAG de-dupe (embeddings), not filename title matching
