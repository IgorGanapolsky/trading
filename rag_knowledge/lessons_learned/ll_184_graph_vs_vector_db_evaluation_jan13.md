# Lesson: Graph Database vs Vector Database for RAG Evaluation

**ID**: ll_184
**Date**: January 13, 2026
**Severity**: LOW
**Category**: architecture-evaluation

## Context
Evaluated whether switching to Graph RAG or hybrid vector+graph approach would benefit our trading system.

## Finding
**REDUNDANT** — Our current Vertex AI RAG with vector embeddings is the correct choice.

## Key Reasons
1. Our data is simple (lessons, trades) — not complex entity networks
2. No multi-hop queries needed ("which lesson → trade → outcome")
3. Volume is small (~1560 lines) — doesn't benefit from graph traversal
4. Trading decisions use momentum signals (90%), not RAG traversal
5. Graph DBs add significant complexity without measurable benefit

## When Graph RAG IS Valuable
- Fraud detection with entity networks
- Multi-hop reasoning (A→B→C→answer)
- Millions of interconnected facts
- Knowledge graphs with complex relationships

## When Vector RAG (What We Have) IS Correct
- Semantic similarity search ✅
- Document retrieval ✅
- Simple Q&A over unstructured text ✅
- Small to medium document collections ✅

## Prevention
Before evaluating database architecture changes, ask:
1. Do we need multi-hop queries? (No)
2. Do we have complex entity relationships? (No)
3. Is our current system failing? (No)

## Tags
`architecture`, `rag`, `vector-database`, `graph-database`, `evaluation`
