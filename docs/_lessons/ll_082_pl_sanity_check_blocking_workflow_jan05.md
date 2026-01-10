---
layout: post
title: "Lesson Learned #082: P/L Sanity Check Was Blocking Entire Workflow"
date: 2026-01-05
---

# Lesson Learned #082: P/L Sanity Check Was Blocking Entire Workflow

**Date**: 2026-01-05
**Severity**: CRITICAL
**Category**: system_integrity

## What Happened

The P/L Sanity Check step in the daily-trading.yml workflow was configured to `exit 1` when it detected "no trades for 3 days". This caused a **chicken-and-egg failure loop**:

1. No trades for 3 days (due to holiday gap Dec 31 - Jan 4)
2. P/L Sanity Check runs with `if: always()` and exits with code 1
3. Entire workflow marked as "FAILED"
4. Workflow failures cascaded - 5 consecutive failures on Jan 5
5. No trades executed because subsequent workflow runs also failed

**Evidence:**
- Runs #429-433 all FAILED on Jan 5, 2026
- `data/trades_2026-01-05.json` never created
- `data/performance_log.json` stuck at Jan 3 entry

## Root Cause

Line 1032 in `.github/workflows/daily-trading.yml`:
```yaml
exit 1  # <-- This killed the entire workflow
```

The P/L Sanity Check was designed to DETECT zombie mode, but it was incorrectly configured to BLOCK the workflow instead of just WARN.

## The Fix

Changed to `continue-on-error: true` and removed `exit 1`:
```yaml
- name: P/L Sanity Check
  if: always()
  continue-on-error: true  # Don't fail workflow - just warn
```

The sanity check now:
- Still detects and logs zombie mode (for monitoring)
- Does NOT block subsequent workflow steps
- Does NOT prevent data commits

## Prevention Rules

1. **Monitoring checks should WARN, not BLOCK**
2. **Use `continue-on-error: true` for non-critical checks**
3. **Never use `exit 1` in monitoring steps that run with `if: always()`**
4. **Test workflow behavior after holiday periods**
5. **Sanity checks should enable debugging, not create new failures**

## Related Lessons

- LL-019: System dead 2 days - overly strict filters
- LL-051: Blind trading catastrophe
- LL-054: RAG not actually used
