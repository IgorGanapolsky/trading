# Lesson: Dead Code Cleanup - January 13, 2026

## Context
Comprehensive codebase audit identified significant technical debt.

## Action Taken
PR #1680 removed 1,088 lines of dead/outdated code:
- `behavioral_finance.py` (708 lines) - ZERO imports anywhere
- `docs/index.md` (62 lines) - outdated CSP strategy
- `docs/_posts/2025-*.md` (317 lines) - stale blog posts

## Verification
- 618 tests passing
- All branches cleaned (only main)
- All PRs merged/closed (0 open)

## Lesson
Run `grep -r "module_name"` BEFORE claiming code is dead.
Follow pre-cleanup protocol from MANDATORY_RULES.md.

## Tags
cleanup, dead-code, technical-debt, audit
