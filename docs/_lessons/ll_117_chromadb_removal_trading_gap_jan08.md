---
layout: post
title: "Lesson Learned #117: ChromaDB Removal Caused 2-Day Trading Gap"
date: 2026-01-08
---

# Lesson Learned #117: ChromaDB Removal Caused 2-Day Trading Gap

**Date**: 2026-01-08
**Category**: CI/CD, RAG System
**Severity**: CRITICAL
**Impact**: No automated trades for Jan 7-8, 2026

## What Happened

ChromaDB was removed from requirements on Jan 7, 2026 (CEO directive to simplify RAG architecture), but the `daily-trading.yml` workflow still had a step that tried to verify ChromaDB installation:

```yaml
- name: Verify ChromaDB (RAG prerequisite)
  run: |
    python3 -c "import chromadb; print(f'✅ ChromaDB v{chromadb.__version__} installed')"
```

This caused the workflow to fail at line 75-79 every time it ran, resulting in **zero automated trades for 2 consecutive trading days**.

## Root Cause

**Incomplete removal**: When removing a dependency:
1. Requirements files were updated (chromadb commented out) ✅
2. RAG scripts were updated to not use chromadb ✅
3. **Workflow verification steps were NOT updated** ❌

The workflow CI would fail silently at the verification step, never reaching the trading execution.

## Impact

- **Jan 7, 2026**: No trades executed (workflow failed)
- **Jan 8, 2026**: No trades executed (workflow still failing)
- **Potential loss**: Missed trading opportunities during 2 market days

## Fix Applied

**PR #1300** removed the ChromaDB verification step and all remaining ChromaDB references:
- Removed `python3 -c "import chromadb"` verification
- Updated comments to note ChromaDB was removed
- Added smoke tests to prevent regression

## Prevention Protocol

When removing ANY dependency:

1. **Search ALL files**: `grep -r "dependency_name" .github/workflows/ src/ scripts/`
2. **Check requirements**: `requirements.txt`, `requirements-minimal.txt`
3. **Check CI workflows**: Especially verification/import steps
4. **Check scripts**: Any pip install commands
5. **Add regression test**: Verify dependency is not imported anywhere

### Mandatory Checklist for Dependency Removal

```
[ ] requirements.txt updated
[ ] requirements-minimal.txt updated
[ ] All workflow pip install commands updated
[ ] All workflow verification steps removed
[ ] All import statements removed from code
[ ] Smoke test added to prevent regression
[ ] CI passes after changes
```

## Evidence

```
# ChromaDB references found AFTER initial removal:
daily-trading.yml:75-79 - import chromadb (verification)
daily-trading.yml:1547 - "ChromaDB AND Vertex AI RAG" comment
phil-town-ingestion.yml:48 - pip install chromadb
weekend-learning.yml:92 - pip install chromadb
```

## Lesson

**Dependency removal is not complete until ALL references are removed from ALL files**, including:
- Requirements files
- CI/CD workflow files
- Scripts that install dependencies
- Verification/test steps

A single missed reference in a CI workflow can silently break the entire system.

## Related Lessons

- LL-009: CI Syntax Failure (Dec 11, 2025) - Similar silent CI failure
- LL-074: RAG Blocking Trading - ChromaDB-related issue
- LL-109: Bidirectional RAG Learning - Vertex AI is the replacement

## Tags

#ci-failure #dependency-removal #chromadb #trading-gap #regression
