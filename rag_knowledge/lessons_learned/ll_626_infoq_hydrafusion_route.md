# LL-626 — Cascade before frontier; isolate the critic

**Date:** 2026-09-15  
**Source:** <https://www.infoq.com/news/2026/09/github-hydrafusion/>  
**PR:** #4690 / AGENT-623

## Lesson

HydraFusion: Single / Cascade / Critique. Cascade drafts cheap then escalates only
on gate failure; Critique uses a tool-less critic then one revision. Five principles:
accounting, bounds, isolated review, fail-safe apply, validated routing. Beats
always-frontier on cost while matching quality.

## Prevention

`scripts/hydrafusion_route.py` / `ralph --hydrafusion-route`.

## Evidence

`pytest tests/test_hydrafusion_route.py`.
