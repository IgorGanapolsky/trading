---
layout: post
title: "Lesson Learned #094: ChromaDB Not Installed - Critical RAG Gap"
date: 2026-01-06
---

# Lesson Learned #094: ChromaDB Not Installed - Critical RAG Gap

**Date**: January 6, 2026
**Severity**: CRITICAL
**Category**: Infrastructure, RAG, Data Recording

## What Happened

During investment strategy review, discovered that ChromaDB was NOT installed on the system. This meant:
- Trades were NOT being recorded to local vector database
- Lessons learned were NOT being vectorized for embedding search
- The "self-healing" RAG system was broken at the foundation

## Evidence

```bash
$ pip show chromadb
WARNING: Package(s) not found: chromadb

$ python3 -c "import chromadb"
ModuleNotFoundError: No module named 'chromadb'

$ ls data/rag/vector_store/
.gitkeep  # EMPTY!
```

## Root Cause

ChromaDB was listed in requirements but was never actually installed in the runtime environment. The vector_store directory only contained a `.gitkeep` placeholder.

## Fix Applied

```bash
pip install chromadb
```

Verified working:
```python
import chromadb
client = chromadb.Client()
collection = client.create_collection('test_collection')
collection.add(documents=['Test trade lesson'], ids=['test1'])
results = collection.query(query_texts=['trade'], n_results=1)
# Query returned: ['Test trade lesson']
```

## Prevention

1. Add ChromaDB installation to session startup hook
2. Add health check to verify vector store has entries
3. CI should verify ChromaDB can import

## Related Files

- `src/rag/vertex_rag.py` - Vertex AI RAG (cloud)
- `src/rag/lessons_learned_rag.py` - Local RAG
- `data/rag/vector_store/` - Vector embeddings directory

## Key Insight

**A RAG system without a working vector database is not a RAG system.**

We had 101 lesson files in markdown but no vector embeddings for semantic search. The system was only doing text-based search (TF-IDF), not true embedding-based retrieval.

## Tags

chromadb, rag, vector_store, infrastructure, critical_fix, data_recording
