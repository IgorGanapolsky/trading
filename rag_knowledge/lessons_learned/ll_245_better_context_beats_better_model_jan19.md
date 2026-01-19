# LL-245: Resource Evaluation - "Better Context Will Always Beat a Better Model"

**Date**: January 19, 2026
**Source**: [The New Stack](https://thenewstack.io/better-context-will-always-beat-a-better-model/)
**Verdict**: REDUNDANT

## What It Proposes
- Context quality matters more than model size
- "Context rot" (accumulated noise) degrades AI performance
- 11.5% accuracy drop when unrelated text added (Mila/McGill study)
- Filtering happens at architecture level, not model level

## Why It's Redundant for Us

We already implement these principles:

| Principle | Our Implementation |
|-----------|-------------------|
| Extract signal | `inject_trading_context.sh` injects only ~30 lines |
| Avoid context rot | Live Alpaca API fetch, not history dumps |
| Filter at architecture | Hook-based injection on UserPromptSubmit |
| Optimal retrieval | Vertex AI RAG: 512 tokens, top-5 results |

## References
- `.claude/hooks/inject_trading_context.sh` - Curated context injection
- `.claude/hooks/mandatory_rag_check.sh` - Filtered critical lessons
- `src/rag/vertex_rag.py` - Optimal RAG configuration

## Decision
No implementation needed. Article validates our existing architecture.

#resource-evaluation #context-management #validated
