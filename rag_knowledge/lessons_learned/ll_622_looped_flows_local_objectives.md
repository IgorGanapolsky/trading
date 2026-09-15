# LL-622 — Looped compute needs local objectives

**Date:** 2026-09-15  
**Source:** <https://arxiv.org/abs/2609.11801> · <https://x.com/omarsar0/status/2098807354343260366>  
**PR:** #4690 / AGENT-623

## Lesson

Looped models fail when gradients only hit the last update — early steps never learn
to set up later ones. Looped flows fix this with local denoising + shared noise.
Agent analog: each Ralph tick needs a local TRUE target (goal-backward fail), not
only end-of-session verify; more `--loop-steps` spends compute on a finer grid.

## Prevention

`scripts/looped_flow_tick.py` / `ralph --looped-flow`. Never train the paper’s model here.

## Evidence

`pytest tests/test_looped_flow_tick.py`.
