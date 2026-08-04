# LL-364: Unify A+ RAG platform instead of parallel open PRs

**Severity**: HIGH  
**Date**: 2026-08-03  
**Tags**: `rag`, `architecture`, `acl`, `chunking`, `observability`, `evaluation`

## What happened

Multiple agents opened parallel "A+" RAG PRs (doc-ingest, retrieval gates, world-class pipeline)
that diverged, left CI checks skipped, and never consolidated into one fail-closed surface.

## Prevention

1. Ship a single `TradingRAGPlatform` facade + `scripts/verify_rag_aplus.py` + `make rag-aplus-check`.
2. Architecture A+ (capability matrix) is separate from measured holdout A+ and trading edge.
3. Wire ACL, traces, OOD reject, and strategy_family into `retrieve_for_trade` and TradeGateway.
4. Do not claim stretch holdout A+ without re-running evaluate_rag on the frozen set.

## Sensitivity

risk_critical
