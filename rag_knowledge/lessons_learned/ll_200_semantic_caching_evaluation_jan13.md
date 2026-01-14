# Semantic Caching for LLM Cost Reduction - Evaluation

**Date:** January 13, 2026
**Severity:** LOW
**Category:** evaluation, cost-optimization
**Source:** VentureBeat article - "Why your LLM bill is exploding — and how semantic caching can cut it by 73%"

## Summary

Semantic caching stores query embeddings + responses to serve cached results when new queries are semantically similar (not just exact matches). Claims 73% cost reduction at 67% hit rate.

## Verdict: REDUNDANT / LOW VALUE

At our current query volume (<50/day), implementation overhead exceeds potential savings.

## Analysis

### Why Not Worth It For Us:

1. **Query Volume Too Low**: ~50 queries/day × $0.01 = $15/month max spend
2. **Already Budget-Optimized**: BATS-style budget tracker in place
3. **Smart Routing Exists**: Most queries bypass LLM entirely:
   - Readiness queries → assess_trading_readiness() (no LLM)
   - P/L queries → get_current_portfolio_status() (no LLM)
   - Only analytical queries hit Vertex AI RAG

### When To Revisit:

- Query volume exceeds 1000/day
- Monthly Vertex AI costs exceed $50
- Customer-facing chatbot with diverse users added

## Implementation Notes (If Needed Later)

Reference implementation from article:
- Use embedding model to vectorize query
- Store (query_embedding, response) pairs
- Similarity threshold tuning per query type
- TTL + event-based cache invalidation

## Prevention

Do not implement complex caching for low-volume systems. Monitor actual costs before optimizing.
