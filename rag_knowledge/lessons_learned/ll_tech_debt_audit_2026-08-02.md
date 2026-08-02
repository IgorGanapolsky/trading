# LL — Technical Debt Audit (2026-08-02)

## Context

CEO ordered comprehensive line-by-line tech debt audit. Full 100% coverage of ~95k
LOC is not claimable in one session. Prior parallel audit branch deleted
`iron-condor-guardian.yml` — rejected.

## Actions landed

- Deleted 7 zero-ref dead scripts (tactical IC / one-offs)
- Neutralized IC entry workflows that still ran on `workflow_dispatch`
- Rewrote `.claude/rules/trading.md` for put-credit active / IC killed
- Prevention tests: `tests/test_killed_ic_workflows.py`
- Report: `reports/tech-debt-audit-2026-08-02.md`

## Rules

1. Never delete guardian workflow without explicit CEO override + replacement exit path
2. `git grep` zero hits is necessary but not sufficient for delete — exclude protected ops scripts
3. Date-series RAG lessons with same title are not duplicates
4. Prefer convert-to-STRATEGY_KILLED no-op over deleting historical kill documentation

## Tags

#tech-debt #cleanup #kill-switch #prevention #workflows
