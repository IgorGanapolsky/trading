# LL: Skipped Prevention Step in Compound Engineering

**Date**: 2026-02-06
**Severity**: CRITICAL (5)
**Category**: Process Violation

## What Happened

PR #3313 added `safe_submit_order()`/`safe_close_position()` wrappers to enforce ticker validation
across 27 files. The fix was correct. The tests passed. But **no CI check was added to prevent
future scripts from bypassing the wrappers**. The CEO had to ask "can't we prevent that?" before
the CI enforcement (PR #3314) was created.

## Root Cause

Skipped step 3 (Prevention) of the compound engineering protocol. Treated the fix + test as
sufficient, when the protocol explicitly requires an automated mechanism to block recurrence.

## Lesson

Prevention is not optional. It is not an afterthought. If someone can write new code that
reintroduces the bug and nothing automated catches it, the fix is incomplete. Period.

## Prevention Applied

1. Updated `.claude/rules/compound-engineering.md` with a mandatory completion gate checklist
2. Added explicit anti-pattern: "Shipping the fix and adding prevention as an afterthought"
3. CI job `Enforce Safe Order Wrappers` now blocks any PR with unprotected order calls

## Severity Justification

Intensity 5 (CRITICAL) — CEO frustration, direct process violation of a rule I'm supposed to follow
automatically. The compound engineering protocol says "No exceptions." I made an exception.
