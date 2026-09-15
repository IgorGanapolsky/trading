# LL-627 — Always-on agents: scope + eval + cheap tiers beat autonomy

**Date:** 2026-09-15  
**Source:** <https://music.youtube.com/watch?v=Xa1jm2VWEHk>  
**PR:** #4690 / AGENT-623

## Lesson

Flat-subscription always-on agents die on unit economics and trust. Highest ROI:
narrow high-frequency workflows, eval-first logging (precision by workflow),
tiered inference (rules before premium), recommend-first with provenance, alert
budgets. Defer general chat and auto-send.

## Prevention

`ops_daily_brief` + `eval_first_ledger` + HydraFusion Cascade. Never auto-send.

## Evidence

`pytest tests/test_ops_daily_brief.py tests/test_eval_first_ledger.py`.
