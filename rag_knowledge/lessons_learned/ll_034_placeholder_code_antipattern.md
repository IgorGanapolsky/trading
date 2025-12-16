# LL-034: Placeholder Code Antipattern

**ID**: LL-034
**Impact**: Identified through automated analysis

**Date**: December 14, 2025
**Category**: Code Quality / Technical Debt
**Severity**: Medium
**Status**: Resolved

## Incident Summary

The codebase accumulated 2,032 lines of placeholder/stub code for LinkedIn and TikTok sentiment integrations that were never implemented. These placeholders:
- Increased code complexity and maintenance burden
- Confused the architecture (5 sources shown, only 3 working)
- Required documentation updates that were never completed
- Added dead imports and unused dependencies

## Root Cause Analysis

1. **Premature Abstraction**: Code was written for "future" features before requirements were clear
2. **No Expiration Policy**: Placeholders had no deadline or review trigger
3. **Missing Verification**: No automated test to detect "not implemented" stubs
4. **Documentation Drift**: Docs showed features that didn't work

## Prevention Measures Implemented

### 1. Pre-commit Hook Detection
Add to `.pre-commit-config.yaml`:
```yaml
- repo: local
  hooks:
    - id: no-placeholder-code
      name: Detect placeholder code
      entry: python scripts/detect_placeholders.py
      language: python
      types: [python]
```

### 2. Dead Code Verification Test
```python
# tests/test_no_dead_code.py
def test_no_not_implemented_functions():
    """Ensure no functions return 'not yet implemented' errors."""
    patterns = [
        "not yet implemented",
        "not implemented",
        "TODO: Implement",
        "placeholder",
    ]
    # Scan codebase for these patterns in return statements
```

### 3. Feature Flag Discipline
- **Rule**: If a feature isn't ready, don't add ANY code for it
- **Alternative**: Use GitHub Issues to track planned features
- **Deadline**: Placeholders must have a removal date in comments

### 4. RAG Query for Periodic Review
```sql
-- Monthly query: Find potential dead code
SELECT file_path, line_number, content
FROM code_index
WHERE content LIKE '%not implemented%'
   OR content LIKE '%TODO%'
   OR content LIKE '%placeholder%'
```

## Verification Checklist

Before adding new integrations, verify:
- [ ] Core functionality is implemented (not stubbed)
- [ ] Tests exist and pass
- [ ] Documentation matches implementation
- [ ] No "coming soon" or placeholder text
- [ ] Config reflects actual capabilities

## Code Removed

| File | Lines Removed | Reason |
|------|---------------|--------|
| `linkedin_collector.py` | ~400 | Never implemented |
| `tiktok_collector.py` | ~500 | Never implemented |
| `docs/linkedin-*.md` | ~200 | Dead documentation |
| `docs/tiktok-*.md` | ~300 | Dead documentation |
| `tests/test_tiktok_*.py` | ~150 | Tests for dead code |
| Various references | ~480 | Cleanup across files |

**Total**: 2,032 lines of dead code removed

## Key Takeaway

> **"Don't write code for features you might build someday. Write code for features you're building today."**

If a feature isn't ready:
1. Create a GitHub Issue instead
2. Don't add placeholder files
3. Don't add "coming soon" documentation
4. Don't add disabled config options

## Tags
`#code-quality` `#technical-debt` `#dead-code` `#prevention` `#cleanup`
