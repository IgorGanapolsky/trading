# LL-621 — GitClear signals: structure over volume

**Date:** 2026-09-15  
**Source:** <https://www.gitclear.com/> · Maintainability Gap  
**PR:** #4690 / AGENT-623

## Lesson

GitClear’s product thesis: AI throughput is real (~+25% vs self) but maintainability
signals slide — duplication↑, moved↓, masking↑, churn↑. Diff Delta (durable change)
beats LOC. Five tripwires beat dashboards.

## Prevention

`scripts/dup_health.py` now emits error_masking, hotspots, churn, diff_delta_proxy,
tripwires. Ralph `--dup-health --churn-days 14 --git-range …`. Never buy GitClear for
this lab.

## Evidence

`pytest tests/test_dup_health.py`; tip push on AGENT-623.
