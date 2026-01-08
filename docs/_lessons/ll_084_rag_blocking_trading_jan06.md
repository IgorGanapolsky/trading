---
layout: post
title: "Lesson Learned: RAG Blocking ALL Trading Due to Overly Aggressive Matching"
date: 2026-01-06
---

# Lesson Learned: RAG Blocking ALL Trading Due to Overly Aggressive Matching

**ID**: LL-084
**Date**: January 6, 2026
**Severity**: CRITICAL
**Category**: Trading
**Impact**: 14 days without paper trading (Dec 23, 2025 - Jan 6, 2026)

## What Happened

1. The `guaranteed_trader.py` script searched RAG for lessons matching "SPY trading failures losses"
2. A CI/CD lesson (LL-CI-001 about test failures) matched the keyword "failures"
3. The script blocked ALL trading because ANY CRITICAL lesson was found
4. Combined with `logging_config.py` deletion, trading was dead for 14 days

## Root Cause

```python
# BUG: Blocked on ANY critical lesson matching "failures"
for lesson, score in spy_lessons:
    if lesson.severity == "CRITICAL":
        return {"success": False, "reason": "blocked_by_rag"}
```

The search query was too generic and the blocking logic didn't filter by category.

## Fix Applied

```python
# FIX: Only block on Trading/Execution/Risk category lessons with high relevance
is_trading_lesson = getattr(lesson, "category", "").lower() in ["trading", "execution", "risk"]
if lesson.severity == "CRITICAL" and is_trading_lesson and score > 0.8:
    return {"success": False, "reason": "blocked_by_rag"}
```

## Prevention

1. **Category filtering**: Only block on lessons from Trading, Execution, or Risk categories
2. **Relevance threshold**: Require score > 0.8 for blocking (not just any match)
3. **Log warnings**: Non-blocking lessons are logged as warnings, not errors
4. **Test coverage**: Added 25 tests for the RAG blocking logic

## Tests Added

- `tests/test_guaranteed_trader_rag.py` - 25 tests covering:
  - CI/CD lessons should NOT block
  - Trading category CRITICAL lessons SHOULD block
  - Low relevance scores should NOT block
  - Missing category should NOT block

## Files Changed

- `scripts/guaranteed_trader.py` - Fixed RAG blocking logic
- `src/utils/logging_config.py` - Restored after accidental deletion
- `tests/test_guaranteed_trader_rag.py` - New test file

## Commits

- PR #1166: "fix: Restore logging_config.py + fix RAG blocking all trading"
