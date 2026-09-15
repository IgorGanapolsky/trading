# LL-620 — AI velocity without dup/refactor gates is a maintainability tax

**Date:** 2026-09-15  
**Source:** <https://thenewstack.io/ai-coding-duplication-rose/>  
**PR:** #4690 / AGENT-623

## Lesson

GitClear’s Maintainability Gap (via TNS): heavy AI use bought ~25% more output while
block duplication rose ~81% and moved/refactor code collapsed (21%→3.8%). Copy-paste
beats extract under fake 10x pressure.

## Prevention

- `scripts/dup_health.py` / `ralph_gsd_tick.py --dup-health`
- Prefer extract/move shared helpers; treat tests+refactor as the mission
- Hygiene already fails on duplicate lesson IDs (LL collision = same class of bug)

## Evidence

`pytest tests/test_dup_health.py`; CI `audit_repository_hygiene` caught LL-618 collision.
