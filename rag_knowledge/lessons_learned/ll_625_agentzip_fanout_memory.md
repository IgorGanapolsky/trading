# LL-625 — Fan-out dies on memory, not CPU

**Date:** 2026-09-15  
**Source:** <https://arxiv.org/abs/2609.11294> · <https://x.com/omarsar0/status/2098531286319341932>  
**PR:** #4690 / AGENT-623

## Lesson

Parallel agent sandboxes share a template; 76–96% of pages are redundant.
Memory is the capacity limit. Prefer shared context fingerprints + worktree
prune over spawning more. Defer heavy GC to LLM-wait windows.

## Prevention

`scripts/agent_fanout_memory.py` / `ralph --fanout-memory --strict`.

## Evidence

`pytest tests/test_agent_fanout_memory.py`.
