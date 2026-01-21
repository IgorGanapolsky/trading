# LL-271: RAG Without Vectors - Article Evaluation

**Date**: January 21, 2026
**Severity**: LOW
**Category**: architecture, rag, evaluation

## Context

Evaluated article: "You Probably Don't Need a Vector Database for Your RAG — Yet" (Towards Data Science)

## Key Insight

The article's thesis: Vector databases (Pinecone, Weaviate, Milvus) are overkill for small RAG systems. Keyword search or in-memory NumPy suffices for <millions of vectors.

## Our Status

**ALREADY IMPLEMENTED** - ChromaDB was removed on Jan 7, 2026 (CEO directive).

Current architecture:
- `lessons_search.py`: Pure keyword search for 110 lessons
- `vertex_rag.py`: Cloud Vertex AI only for Dialogflow voice integration

## Why This Matters

Confirms our Jan 7, 2026 decision was correct. We avoided:
- Unnecessary complexity
- Extra latency
- Serialization overhead
- Vector DB management burden

## Prevention

When evaluating new RAG tools/techniques:
1. Check if we already have a simple solution
2. Calculate actual corpus size (110 lessons = trivial)
3. Don't add vector DBs until corpus exceeds 100K+ documents
4. Keyword search + recency boost handles most use cases

## Tags

`architecture`, `rag`, `evaluation`, `redundant`
