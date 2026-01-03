---
layout: lesson
title: "GitHub Pages Showed Stale Portfolio Data"
date: 2026-01-03
category: automation
severity: medium
tags: [github-pages, automation, stale-data, prevention]
---

# Lesson: GitHub Pages Showed Stale Portfolio Data

## The Failure

On January 3, 2026, discovered that GitHub Pages (iganapolsky.github.io/trading) was displaying portfolio data from December 29 instead of the current December 30 data:

- **Displayed**: $100,810.04 (+0.81%), 50% win rate, 66 lessons
- **Actual**: $100,942.23 (+0.94%), 80% win rate, 74 lessons

The site was 4 days behind, showing inaccurate information to the public.

## Root Cause

The `docs/index.md` file had **hardcoded values** that were not automatically updated. The Daily Transparency Report table contained static numbers that required manual updates.

```markdown
| **Portfolio** | $100,810.04 | +0.81% |  <!-- HARDCODED! -->
| **Win Rate** | 50% | Stable |           <!-- HARDCODED! -->
| **Lessons** | 66+ | Growing |            <!-- HARDCODED! -->
```

## Impact

- Public website showed inaccurate financial data
- Win rate displayed as 50% instead of actual 80%
- Lessons count 8 behind (66 vs 74)
- Undermines trust in transparency commitment

## The Fix

1. **Immediate**: Updated docs/index.md with current values (PR #1008)
2. **Prevention**: Created `scripts/update_github_pages.py` to auto-update docs/index.md
3. **Automation**: Added step to daily-trading.yml workflow

## Prevention Implemented

### New Script: `scripts/update_github_pages.py`

Automatically updates docs/index.md by:
- Reading current values from `data/system_state.json`
- Counting lessons in `docs/_lessons/`
- Using regex to replace values in the markdown table
- Only modifying file if values changed

### Workflow Integration

Added to `.github/workflows/daily-trading.yml`:

```yaml
- name: Update GitHub Pages Data
  run: |
    python3 scripts/update_github_pages.py
    # Auto-commit if changed
```

### Test Coverage

Created `tests/test_update_github_pages.py` with 27 tests covering:
- Currency formatting
- Percentage formatting
- State loading
- Lesson counting
- Index.md updating
- Edge cases

## Key Lesson

**Never hardcode values that change.** If data is displayed from a source, automate the sync. Manual updates will always fall behind.

## Prevention Checklist

- [x] Script to auto-update docs/index.md
- [x] 100% test coverage (27 tests)
- [x] Integration with daily workflow
- [x] Lesson documented

## Related Lessons

- ll_042_code_hygiene_automated_prevention_dec15.md
- ll_044_documentation_hygiene_mandate_dec15.md
