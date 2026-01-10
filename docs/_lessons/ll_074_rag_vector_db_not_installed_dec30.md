---
layout: post
title: "Lesson Learned #074: RAG Vector DB Package Not Installed Despite Being in Requirements"
date: 2025-12-30
---

# Lesson Learned #074: RAG Vector DB Package Not Installed Despite Being in Requirements

**ID**: LL-074
**Date**: December 30, 2025
**Severity**: HIGH
**Category**: infrastructure, rag, ml

## Incident

RAG was not working because chromadb was listed in requirements-minimal.txt but NOT actually installed in the runtime environment. System fell back to TF-IDF keyword matching instead of semantic embeddings.

## Evidence

```bash
# In requirements-minimal.txt:
chromadb==0.6.3

# But in runtime:
$ pip show chromadb
WARNING: Package(s) not found: chromadb

$ python3 -c "import chromadb"
ModuleNotFoundError: No module named 'chromadb'

# RAG stats showing TF-IDF fallback:
{
  "using_fastembed": false,
  "using_lancedb": false,
  "using_tfidf": true  ← FALLBACK MODE
}
```

## Root Cause

1. chromadb was in requirements-minimal.txt and requirements-rag.txt
2. Main requirements.txt did NOT include chromadb
3. Local/dev environment installed from requirements.txt, not requirements-minimal.txt
4. No verification that vector DB packages were actually available at runtime

## Impact

- RAG returned empty or keyword-only results
- Lessons learned were not semantically searchable
- System couldn't learn from past mistakes effectively
- CEO lost trust in system's ability to learn

## Fix Applied

```bash
pip install chromadb==0.6.3
rm -rf data/vector_db  # Clear incompatible old DB
python3 scripts/vectorize_rag_knowledge.py --rebuild
```

Result: 704 chunks vectorized, semantic search working.

## Prevention

1. **Add chromadb to main requirements.txt** (not just minimal/rag variants)
2. **Add startup check**: Verify chromadb imports before any RAG operations
3. **CI verification**: Test that RAG queries return semantic results, not empty
4. **Health check**: `scripts/system_health_check.py` should verify vector DB

## Verification Commands

```bash
# Verify chromadb installed
python3 -c "import chromadb; print('OK:', chromadb.__version__)"

# Verify vector DB has data
python3 scripts/vectorize_rag_knowledge.py --stats

# Test semantic search
python3 scripts/vectorize_rag_knowledge.py --query "margin of safety"
```

## Tags
`rag` `vector-db` `chromadb` `infrastructure` `silent-failure`
