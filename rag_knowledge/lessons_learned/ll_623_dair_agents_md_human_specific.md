# LL-623 — AGENTS.md: human-specific or it hurts

**Date:** 2026-09-15  
**Source:** <https://academy.dair.ai/dashboard/resources/agents-md-evaluation> · arXiv:2602.11988  
**PR:** #4690 / AGENT-623

## Lesson

ETH Zurich (via DAIR): human-written context files ~+4% success; LLM-generated ~−2%;
any context file adds ~20% inference cost. Redundant README restatement is the failure
mode. Write for the gap (non-obvious tooling), not the overview.

## Prevention

`scripts/agents_md_health.py` — size budget, README overlap, LLM tells, additive markers.
Daily DAIR implement rail tickets this class of steals.

## Evidence

`pytest tests/test_agents_md_health.py` — 3 passed; live Agents.md ok (additive≥5).
