---
layout: post
title: "Lesson Learned: Trade Files Not Committed to Repo (Dec 12, 2025)"
---

# Lesson Learned: Trade Files Not Committed to Repo (Dec 12, 2025)

**ID**: LL-020
**Date**: December 12, 2025
**Severity**: HIGH
**Category**: Workflow, Data Loss
**Impact**: Confusion about whether trades were executing; data not persisted

## Prevention Rules

1. Always commit all trading data files (trades_*.json, system_state.json, performance_log.json)
2. Add explicit git add commands for all data files in workflows
3. Verify commits contain expected files before marking workflow as successful

## What Happened

Trade files (`data/trades_YYYY-MM-DD.json`) were being created during workflow execution but NOT committed to the repository. This caused confusion about whether trades were actually executing.

**Timeline:**
- Dec 10: Last trade file in repo: `trades_2025-12-10.json`
- Dec 12 14:37: Daily trading workflow ran successfully (all steps passed)
- Dec 12 14:55: Artifacts contain trade data, but no `trades_2025-12-12.json` in repo

**Evidence:**
- Workflow artifacts show `trading-logs-20170130041` (17,883 bytes)
- Execute daily trading step: SUCCESS
- Update performance log step: SUCCESS
- Verify Positions step: SUCCESS
- P/L Sanity Check step: SUCCESS
- BUT: No `trades_2025-12-12.json` committed to repo

## Root Cause

The "Commit system state updates" step only staged `system_state.json`:

```yaml
# WRONG - Only commits system_state.json
git add data/system_state.json
```

Trade files (`trades_*.json`) and performance log updates were NOT staged or committed.

## Prevention Fix

Updated the step to commit ALL trading data:

```yaml
- name: Commit trading data updates
  run: |
    # Stage ALL trading data files
    git add data/system_state.json data/performance_log.json data/trades_*.json 2>/dev/null || true

    # Check if there are changes to commit
    if git diff --cached --quiet; then
      echo "No trading data changes to commit"
      exit 0
    fi

    # Commit with descriptive message
    TODAY=$(date +%Y-%m-%d)
    git commit -m "chore: Update trading data ($TODAY)"
    git push origin main
```

## Verification

After this fix, every successful trading run should:
1. Have `data/trades_{today}.json` committed to repo
2. Have `data/performance_log.json` updated with today's entry
3. Have `data/system_state.json` updated

## Related Issues

- LL-019: Trading system dead for 2 days (detected because no trade files)
- Trade files were being created but not committed, masking the issue

## Tags
`workflow` `data` `trades` `commit` `bug-fix` `ci`
