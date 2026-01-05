---
layout: post
title: "Lesson Learned #079: ChromaDB Not Actually Installed Despite CI Passing"
date: 2026-01-05
---

# Lesson Learned #079: ChromaDB Not Actually Installed Despite CI Passing

**ID**: LL-079
**Date**: January 5, 2026
**Severity**: HIGH
**Category**: infrastructure, rag, ml, silent-failure

## Incident

ChromaDB was not installed in the runtime environment despite:
1. Being listed in requirements-minimal.txt and requirements-rag.txt
2. CI tests passing (mocked imports)
3. vectorized_files.json showing 133 files vectorized

The system fell back to useless TF-IDF keyword matching, making semantic search impossible.

## Evidence

```bash
# Before fix:
$ python3 -c "import chromadb"
ModuleNotFoundError: No module named 'chromadb'

# RAG stats showed TF-IDF fallback:
2026-01-05 - ERROR - ChromaDB not installed. Run: pip install chromadb
📊 RAG Vectorization Stats:
   Last updated: 2026-01-05T11:21:12
   Files vectorized: 133  ← BUT NOT ACTUALLY SEARCHABLE!

# After fix:
$ python3 -c "import chromadb; print('OK:', chromadb.__version__)"
OK: 0.6.3

$ python3 scripts/vectorize_rag_knowledge.py --rebuild
✅ Vectorization complete!
   Files processed: 136
   Chunks created: 721
```

## Root Cause

1. ChromaDB was in optional requirements files (requirements-rag.txt, requirements-minimal.txt)
2. Main requirements.txt did NOT include ChromaDB
3. No startup verification that semantic search actually works
4. Lesson #074 from Dec 30 warned about this EXACT problem but it wasn't fixed in main requirements.txt

## Impact

- RAG queries returned keyword-match results only (not semantic)
- Lessons learned about "stale data lying" couldn't be found by queries about "profit calculation errors"
- System repeated same mistakes because knowledge wasn't searchable
- CEO lost trust in system's ability to learn from failures

## Fix Applied

```bash
pip install chromadb==0.6.3
python3 scripts/vectorize_rag_knowledge.py --rebuild
```

Result: 721 chunks vectorized, 6/6 tests passing, semantic search working.

## Prevention

1. Add `chromadb>=0.6.0` to main requirements.txt (not just optional files)
2. Startup hook already exists (`verify_vector_db.sh`) but needs to FAIL LOUDLY
3. Add to system health check: verify semantic search returns results

## Verification Commands

```bash
# 1. Verify ChromaDB installed
python3 -c "import chromadb; print('OK:', chromadb.__version__)"

# 2. Verify semantic search works
python3 scripts/vectorize_rag_knowledge.py --query "margin of safety"

# 3. Run all RAG tests
python3 -m pytest tests/test_rag_vector_db.py -v
```

## Tags

`rag` `chromadb` `silent-failure` `semantic-search` `infrastructure`

## Related Lessons

- LL-074: RAG Vector DB Package Not Installed (Dec 30) - same root cause
- LL-054: RAG Was Built But Not Used (Dec 17) - keyword matching is useless
- LL-076: ChromaDB v0.6.0 API Changes (Jan 4)
