# Lesson Learned #093: RLHF Storage Completely Broken - Missing Dependencies

**ID**: LL-093
**Date**: January 6, 2026
**Severity**: CRITICAL
**Category**: infrastructure, rlhf, learning

## What Happened

CEO asked if we are recording trades to Vertex RAG and ChromaDB.

Investigation revealed ALL learning storage is broken:

```bash
$ pip show chromadb
WARNING: Package(s) not found: chromadb

$ python3 -c "from src.learning.rlhf_storage import store_trade_trajectory"
ModuleNotFoundError: No module named 'numpy'
```

## Impact

- **Every trade since Dec 2025** has NOT been recorded to vector databases
- **No learning from mistakes** - system cannot improve
- **RLHF trajectories lost** - cannot train reward models
- **North Star unreachable** - cannot compound learnings

## Root Cause

Dependencies not installed in sandbox environment:
- `numpy` - Required for RLHF storage
- `chromadb` - Local vector database
- `lancedb` - RLHF trajectory storage

## What IS Working

- ✅ Local JSON files (`data/trades_*.json`)
- ✅ Markdown RAG lessons (102 files)
- ✅ `data/system_state.json` backup

## Fix Required

```bash
pip install numpy chromadb lancedb
```

## Prevention

1. Add dependency check to session startup hook
2. Alert if any learning storage fails
3. Graceful degradation with warning, not silent failure

## CEO Directive Violated

From CLAUDE.md:
> "Record every trade and lesson in BOTH ChromaDB AND Vertex AI RAG (MANDATORY)"

This has NOT been happening. Immediate fix required.

## Tags

rlhf, chromadb, vertex_ai, dependencies, critical_fix, learning
