# LL-573 — ExplainX trending is their traffic, not our ROI

**Date:** 2026-09-04
**Severity:** 3
**Linear:** AGENT-573

## Mistake class

Treating <https://explainx.ai/trending> as a skill-install feed or inventing
TF-IDF "ROI" on hardcoded titles (mac-yolo `explainx-trending-rag-engine.js`).

## Correction

Parse the live/fixture `score` field. Map onto existing rails or SKIP.
Zero items → UNAVAILABLE. Never auto-install. `/limit-reset` means two
ceilings: daily structures ≠ cohort n=30. Planner (dry-run) ≠ executor
(TradeGateway). Live stays blocked.

## Prevention

`tests/test_explainx_trending.py` fails closed on empty HTML, invented
resets, live `--live`, and lookalike TF-IDF snippets.
