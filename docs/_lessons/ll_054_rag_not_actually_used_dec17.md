---
layout: post
title: "Lesson Learned: RAG Was Built But Not Used - Keyword Matching is Useless"
date: 2025-12-17
---

# Lesson Learned: RAG Was Built But Not Used - Keyword Matching is Useless

**ID**: ll_054
**Date**: 2025-12-17
**Severity**: CRITICAL
**Category**: RAG, ML, Operational Failure Prevention

## Problem Statement

We had **60 lessons learned** in RAG but kept repeating the same failures because:
1. The trade gate was doing **keyword matching** instead of **semantic search**
2. Queries like "SPY trading" would NEVER find lessons about "blind trading catastrophe"
3. No context-aware blocking (equity=$0 didn't trigger the blind trading lesson)
4. No pre-session check to review recent CRITICAL lessons

## Root Cause

The `_query_rag_for_lessons` method in `mandatory_trade_gate.py` was doing:

```python
# BAD - Simple keyword search (USELESS)
for lesson_file in lessons_dir.glob("*.md"):
    content = lesson_file.read_text().lower()
    for query in queries:
        if query.lower() in content:  # This will NEVER find relevant lessons!
```

With queries like:
- `"SPY trading"` - Won't find "blind trading catastrophe"
- `"equities strategy"` - Won't find "options not closing properly"
- `"buy order mistakes"` - Won't find "API method mismatch"

## The Fix

### 1. Semantic Search with LessonsSearch

```python
# GOOD - Use semantic search engine
semantic_queries = [
    "operational failure trading",
    "blind trading account data reading failure",
    "portfolio sync error equity zero",
    "API connection failure trade blocked",
]

for query in semantic_queries:
    results = self.lessons_search.query(query, top_k=2)
    # Process results with relevance scoring
```

### 2. Context-Aware Blocking

```python
# Block trades when operational context matches lessons
if equity is not None and equity <= 0:
    blocked = True
    block_reasons.append("BLOCKED: Equity is $0 - ll_051 blind trading prevention")
```

### 3. Pre-Session RAG Check

New script `scripts/pre_session_rag_check.py` runs before every trading session to:
- Find CRITICAL lessons from the past 14 days
- Warn about unresolved operational failures
- Force humans/AI to read lessons before trading

### 4. Critical Lesson Detection at Startup

Trade gate now checks for CRITICAL lessons on initialization:

```python
def _check_recent_critical_failures(self) -> None:
    """Check for recent CRITICAL operational failures at startup."""
    # Query RAG for recent critical failures
    # Log warnings about lessons that should be reviewed
```

## Verification

Tests in `tests/test_rag_actually_works.py` verify:
1. Lessons exist and are indexed
2. Semantic search actually finds relevant lessons
3. Gate blocks when equity=$0 (blind trading prevention)
4. Pre-session check runs and finds CRITICAL lessons

## Prevention Rules

1. **ALWAYS use semantic search** - Never do keyword matching on lessons
2. **Context-aware blocking** - Pass operational state (equity, buying_power) to gate
3. **Pre-session checks** - Query RAG for recent failures BEFORE trading
4. **Test that RAG works** - Add tests that verify lessons are actually found

## Files Changed

- `src/safety/mandatory_trade_gate.py` - Semantic search, context-aware blocking
- `src/execution/alpaca_executor.py` - Pass context to trade gate
- `scripts/pre_session_rag_check.py` - NEW: Pre-session lesson review
- `.github/workflows/daily-trading.yml` - Added pre-session RAG check
- `tests/test_rag_actually_works.py` - NEW: Verify RAG actually works

## Key Insight

**Building a knowledge base is worthless if you don't query it properly.**

We spent hours building RAG, indexing 60 lessons, and setting up vector stores.
But the actual query logic was doing dumb keyword matching that found nothing.

The same pattern applies to ML:
- Train an anomaly detector ✓
- Deploy it to production ✓
- **Actually call it with relevant features** ✗

This lesson is about ensuring tools are not just built, but USED CORRECTLY.

## Tags

`rag`, `semantic_search`, `lessons_learned`, `operational_failure`, `blind_trading`, `context_aware`, `pre_session_check`
