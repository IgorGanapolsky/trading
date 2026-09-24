---
id: LL-672
date: 2026-09-23
severity: high
status: active
category: agent-engineering
---

# LL-672: Autonomous Ralph Loop and pstack Engineering Framework

**Date**: September 23, 2026  
**Author**: CTO (Claude) | CEO: Igor Ganapolsky  
**Category**: agent-engineering  

## Summary

To achieve robust, autonomous problem-solving without hallucinated completion, premature victory declarations, or endless circular regressions, the engineering operations have integrated the **Ralph Loop** pattern and Lauren Tan's **pstack** methodology. Furthermore, coordination and planning lean on the external sources of truth: Linear, the shared Obsidian Vault, Gemini/Workflow Notebooks, and Git worktrees.

## The Ralph Loop Methodology

1. **Deterministic Finish Condition**: Every engineering cycle starts with a machine-verifiable exit criterion (e.g., test suite exit code 0, specific metric threshold, zero lint errors, dry-run passing).
2. **One Hypothesis, One Mutation**: Take exactly 1 justified action per iteration. Never bundle speculative refactoring with defect fixes.
3. **Prove It Works**: Test against real runtime interfaces (`make check`, `scripts/system_health_check.py`, `pytest`), not synthetic mocks.
4. **Immediate Revert on Regression**: If an iteration regresses or fails to advance toward the finish condition, revert changes immediately (`git restore`). Never build on top of broken state.
5. **TSV Decision Trail**: Every cycle logs a row to `data/audit/decision_log.tsv` capturing timestamp, iteration, hypothesis, action, evidence, and result.
6. **Struggle Detector & Circuit Breaker**: If 3 consecutive iterations produce the same error, or 3 iterations show zero progress, halt the loop and pivot strategy.

## pstack Skills Implemented

- `skills/ralph-loop`: Autonomous test-driven execution loop with struggle detection and TSV decision trails.
- `skills/pstack-how`: Read-only runtime tracing and subsystem mental model generation without code modifications.
- `skills/pstack-why`: Deep historical archaeology using Git blame, PR discussions, and RAG lessons.
- `skills/pstack-architect`: Caller-first interface design with pre-implementation checkpoints.
- `skills/pstack-arena`: Isolated multi-worktree candidate implementations scored against a deterministic rubric.
- `skills/pstack-interrogate`: Diff interrogation sorting findings into `act on`, `consider`, `noted`, and `dismissed`.
- `skills/verify-trading`: 6-layer operational verification playbook ("Prove It Works").

## Multi-Agent Planning & Coordination Integration

- **Linear**: Authoritative for task scoping, issue assignment, status, and blockers (using personal identity `IGO-XXX` or `AGENT-XXX`).
- **Shared Obsidian Vault**: Authoritative for active claims (`Handoffs/linear-claims/`), agent status, and memory.
- **Workflow / Gemini Notebooks**: Goal formulation, reviewed plans, structured decision trails, and discoverable indexes.
- **Git Worktree & PR**: Authoritative record of code changes, branch protection, CI checks, and merge evidence.
