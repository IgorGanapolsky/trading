# Lesson Learned: Safe Dead Code Cleanup Using pre_cleanup_check.py

**ID**: LL_140
**Date**: 2026-01-13
**Severity**: MEDIUM
**Category**: Process
**Tags**: cleanup, dead-code, technical-debt, safety, ci

## Incident Summary

Successfully deleted 2,325 lines of dead code (2 files + 7 archived .md files) without breaking CI by using the `pre_cleanup_check.py` script to verify no dependencies before deletion.

## Root Cause

Dead code accumulates over time when:
1. Modules are replaced but old versions kept (e.g., `core/risk_manager.py` duplicated by `risk/risk_manager.py`)
2. Large feature modules become unused when simpler alternatives are adopted (e.g., `iv_data_integration.py` replaced by `iv_data_provider.py`)
3. Archived reports and posts are never cleaned up

## Impact

- **Before**: 2,988 lines of dead code bloating codebase
- **After**: Clean deletion without CI failures
- **Benefit**: Reduced maintenance burden, clearer codebase

## Prevention Measures

1. **Always run pre_cleanup_check.py before deleting code**:
   ```bash
   python3 scripts/pre_cleanup_check.py src/module_to_delete.py
   ```

2. **Check for try/except wrapped imports** - These are safe to delete as the import will silently fail

3. **Update `__init__.py` files** after deleting modules that were re-exported

4. **Run tests after deletion** to verify no regressions

## Detection Method

- Comprehensive code audit using `grep -r` to find unused imports
- Comparing duplicate modules to identify the "active" vs "dead" version
- Checking file line counts to identify large candidates for review

## Related Lessons

- LL_137: Branch and PR Hygiene
- LL_138: Technical Debt Audit
