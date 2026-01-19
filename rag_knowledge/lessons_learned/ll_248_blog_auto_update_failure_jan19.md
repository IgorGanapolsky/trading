# LL-248: Blog Auto-Update Script Using Wrong JSON Paths

**Date**: 2026-01-19
**Category**: Bug, Data Integrity
**Severity**: MEDIUM

## Summary

GitHub Pages blog displayed stale data from Day 78 (Jan 16) instead of Day 84 (Jan 19) because the auto-update script expected different JSON structure than system_state.json provides.

## Root Cause

The `scripts/update_github_pages.py` script expected:
```python
# EXPECTED (OLD)
account = state.get("account", {})
equity = account.get("current_equity", 100000.0)
```

But system_state.json provides:
```python
# ACTUAL (CURRENT)
paper_account = state.get("paper_account", {})
equity = paper_account.get("equity", 5000.0)
```

Additionally, the regex patterns were designed for a different index.md format with `| **Portfolio** | $XXX |` tables, not the simple `| Paper Account | $XXX |` format.

## Impact

- Blog showed $5,007.98 instead of $4,986.39
- Blog showed +$7.98 profit instead of -$13.61 loss
- Blog showed Day 78 instead of Day 84
- Users/CEO saw outdated, incorrect information

## Fix Applied

1. Updated script to use `paper_account.*` JSON paths
2. Updated regex patterns to match current simple table format
3. Added `total_pl` and `positions_count` to updates
4. Added fallback to `rag_knowledge/lessons_learned` for lesson count

## Prevention

1. **Schema documentation**: Document expected JSON structure in script comments
2. **Test coverage**: Add tests that verify script can parse current system_state.json
3. **CI validation**: Workflow should fail if update_github_pages.py can't find expected data

## Related

- LL-218: Dashboard 100K bug (similar data mismatch issue)
- LL-230: Trade data source priority bug

## Tags

`bug`, `medium`, `blog`, `data-integrity`, `json-schema`
