# LL-630 — HydraFusion must execute, not only plan

**Date:** 2026-09-15  
**Source:** <https://www.infoq.com/news/2026/09/github-hydrafusion/>  
**PR:** #4690 / AGENT-623

## Lesson

Route-only HydraFusion does not buy Cascade savings. Must execute: gate pass skips
escalation; critic stays tool-less; fail-safe rejects bad validation; accounting
records spent vs planned cost units.

## Prevention

`scripts/hydrafusion_execute.py` in integrated tick + ralph `--hydrafusion-execute`.

## Evidence

`pytest tests/test_hydrafusion_execute.py` — Cascade early-exit legs=[drafter,gate]; Critique isolated.
