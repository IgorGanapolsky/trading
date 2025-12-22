---
layout: post
title: "Lesson Learned #047: RAG Dual Database Cleanup Needed"
date: 2025-12-15
---

# Lesson Learned #047: RAG Dual Database Cleanup Needed

**ID**: LL-047
**Impact**: Identified through automated analysis

**Date**: December 15, 2025
**Severity**: MEDIUM
**Category**: Technical Debt, RAG, Infrastructure
**Status**: IDENTIFIED (cleanup pending)

---

## The Problem

We have **two RAG vector databases** in the codebase:

| Database | Files Using | Status |
|----------|-------------|--------|
| ChromaDB | 2 files | Legacy |
| LanceDB | 3 files | Newer |

This creates:
- Confusion about which to use
- Double dependencies
- Inconsistent behavior
- CI failures when one is missing

## How We Got Here

1. Started with ChromaDB (legacy)
2. Someone added LanceDB (newer, simpler)
3. Neither was fully migrated
4. Both are now "required"

## Today's Fix (Bandaid)

Added both to `requirements-minimal.txt`:
```
chromadb==0.6.3
lancedb>=0.4.0
```

This fixes CI but doesn't solve the underlying mess.

## Recommended Cleanup (TODO)

### Option A: Consolidate to LanceDB (Recommended)

**Why LanceDB**:
- Simpler API
- No server needed
- Better for embeddings
- More modern

**Steps**:
1. Migrate ChromaDB code to LanceDB
2. Remove ChromaDB from requirements
3. Test RAG functionality
4. Delete old ChromaDB files

### Option B: Consolidate to ChromaDB

**Why ChromaDB**:
- More established
- Better documentation
- Larger community

**Steps**:
1. Migrate LanceDB code to ChromaDB
2. Remove LanceDB from requirements
3. Test RAG functionality
4. Delete old LanceDB files

## Files to Review

**ChromaDB users**:
- `rag_store/vector_store.py`
- `src/rag/unified_rag.py`

**LanceDB users**:
- `src/rag/lessons_indexer.py`
- `src/rag/lightweight_rag.py`
- `src/rag/lessons_search.py`

## Priority

- **P2** - Not urgent but creates technical debt
- Cleanup in next sprint (Week 4)

## Tags

`rag`, `technical_debt`, `chromadb`, `lancedb`, `cleanup`
