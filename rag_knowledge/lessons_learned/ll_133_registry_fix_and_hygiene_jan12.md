# LL-133: Lesson Learned #133: Registry.py Missing Broke All Trading Strategies

**Date:** January 12, 2026
**Author:** CTO Claude
**Category:** Critical Bug Fix
**Severity:** P0 - System Breaking

## Incident

During a system health check, discovered that `src/strategies/registry.py` was deleted in the NUCLEAR CLEANUP PR (#1445) but `src/strategies/__init__.py` still imports from it.

**Impact:**
- ALL trading strategies were broken with `ImportError`
- Phil Town strategy could not execute
- Paper trading was non-functional

## Root Cause

Code cleanup PR deleted files without checking for cross-module dependencies. The `__init__.py` file was not updated to remove the import.

## Resolution

1. Created stub file `src/strategies/registry.py` with minimal implementations
2. Verified imports work
3. PR #1469 created (auto-closed as PR #1470 already had the fix)

## Prevention

1. **Pre-cleanup safety check**: Added in PR #1470 to verify imports before cleanup
2. **Dry run protocol**: Always run `python3 -c "from src.orchestrator.main import TradingOrchestrator"` after merges

## Additional Findings This Session

### Branch Cleanup
- Deleted 2 stale branches:
  - `claude/research-trading-playbook-BopBV` (same as main)
  - `claude/research-trading-security-IKyrD` (44 commits behind)

### Hygiene Status
- 0 log files
- pycache cleaned
- No syntax errors in src/

### RAG Status
- 321 lesson files deleted in NUCLEAR CLEANUP
- Only 3 lessons remain
- Vertex AI sync workflows exist and are configured

## Key Takeaway

**NEVER delete files without verifying all imports are updated.**

The trading system was silently broken - no one would have known until the 9:35 AM trading run failed.
