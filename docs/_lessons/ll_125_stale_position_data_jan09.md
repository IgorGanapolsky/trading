---
layout: post
title: "Lesson Learned #125: Stale Position Data Inconsistency (Jan 9, 2026)"
date: 2026-01-09
---

# Lesson Learned #125: Stale Position Data Inconsistency (Jan 9, 2026)

**Date**: January 9, 2026
**Severity**: HIGH
**Category**: Data Integrity
**Status**: FIXED

## Summary

CEO caught inconsistency: system_state.json showed 5 open positions in `performance.open_positions` but `paper_account.positions_count: 0`. This was stale data from BEFORE the Jan 7 reset.

## The Problem

```json
// Paper account (correct):
"positions_count": 0,
"win_rate_warning": "FRESH START - No trades yet after reset"

// Performance section (STALE):
"open_positions": [
  {"symbol": "SPY", ...},   // STALE - from before reset
  {"symbol": "INTC260109P00035000", ...},
  ...
]
```

## Root Cause

When CEO reset the paper account on Jan 7, 2026:
1. `paper_account` section was updated correctly to show $5K fresh start
2. `performance.open_positions` was NOT cleared
3. This created misleading data about "unrealized gains at risk"

## Fix Applied

Cleared `performance.open_positions` array with note explaining the fix.

## Prevention

When resetting any account:
1. Update account balance section
2. Clear performance.open_positions
3. Clear related trade metrics
4. Add audit note with timestamp

## CEO Lesson

The CEO asked: "Are you sure you are talking about $5K paper trading account?"

This question caught the inconsistency. Always verify data across ALL sections of system_state.json, not just one.

## Tags

data-integrity, stale-data, paper-trading, system-state
