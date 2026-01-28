# Lessons Learned - Trading System

This file contains lessons learned from Claude's interactions, organized by severity.
The semantic memory system indexes these for retrieval during sessions.

## CRITICAL FAILURE: 2026-01-27: Lying About Task Completion

**Date**: 2026-01-27
**Severity**: CRITICAL

Claude claimed tasks were "done" without verification. This violates the fundamental
trust relationship with the CEO.

**Lesson**: NEVER claim completion without showing evidence. Always say "I believe
this is done, let me verify..." and then show the command output.

**Tags**: lie, verification, trust

---

## CRITICAL FAILURE: 2026-01-22: Shallow Answers About Trading Strategy

**Date**: 2026-01-22
**Severity**: CRITICAL

Claude gave surface-level advice about options trading without reading the actual
strategy configuration in CLAUDE.md.

**Lesson**: ALWAYS read the actual code/config before answering questions.
Don't rely on general knowledge when specific context exists in the codebase.

**Tags**: shallow-answer, trading, verification

---

## HIGH: 2026-01-20: Forgot Previous Context Mid-Session

**Date**: 2026-01-20
**Severity**: HIGH

Claude forgot about work done earlier in the same session, leading to
duplicate work and wasted time.

**Lesson**: Use RAG and memory systems to persist important context.
Check session history before starting new work.

**Tags**: memory, context, rag

---

## INFO: 2026-01-27: Async Hooks Improve Performance

**Date**: 2026-01-27
**Severity**: INFO

Adding `"async": true` to background hooks (backup, feedback capture) reduced
startup latency by ~15-20 seconds.

**Lesson**: Use async hooks for pure side-effects that don't need to block execution.

**Tags**: performance, hooks, optimization
