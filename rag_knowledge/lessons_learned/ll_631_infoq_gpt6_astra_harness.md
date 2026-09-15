# LL-631 — Astra harness patterns without Astra API primary

**Date:** 2026-09-15  
**Source:** <https://www.infoq.com/news/2026/09/openai-gpt6-astra/>  
**PR:** #4690 / AGENT-623

## Lesson

Astra’s ROI for us is harness: searchable notes across windows, confirm
consequential actions, computer-use rails, evidence-before-claim. The model’s
cyber class and API cost are reasons to fail-closed — never default primary.

## Prevention

`astra_harness_gate` + `astra_session_notes` in integrated tick.

## Evidence

pytest tests/test_astra_harness.py.
