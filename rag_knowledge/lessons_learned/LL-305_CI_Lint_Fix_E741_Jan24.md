# LL-305: CI Lint Fix - Ambiguous Variable Name (E741)

**Date**: January 24, 2026
**Category**: CI / Code Quality
**Severity**: MEDIUM

## Problem

CI was failing on the `Lint & Format` job with error:
```
scripts/ralph_discovery_blog.py:158:17: E741 Ambiguous variable name: `l`
```

The variable `l` (lowercase L) is flagged by ruff as ambiguous because it looks similar to:
- The number `1`
- The pipe character `|`
- The uppercase `I`

## Solution

Renamed the variable from `l` to `line` for clarity:

```python
# Before (failing)
non_header_lines = [
    l.strip()
    for l in lines
    if l.strip() and not l.startswith("#")
]

# After (passing)
non_header_lines = [
    line.strip()
    for line in lines
    if line.strip() and not line.startswith("#")
]
```

## Key Insight

The CI runs `ruff check .` on the **entire repository**, not just `src/`. When running locally, ensure you check the full repo:

```bash
# Correct - checks entire repo
ruff check . --output-format=github

# Incomplete - misses scripts/
ruff check src/
```

## Prevention

1. Always run `ruff check .` (not `ruff check src/`) before committing
2. Pre-commit hooks should be configured to run on all Python files
3. Avoid single-letter variable names, especially `l`, `O`, `I`

## Tags

`ci`, `lint`, `ruff`, `E741`, `code-quality`
