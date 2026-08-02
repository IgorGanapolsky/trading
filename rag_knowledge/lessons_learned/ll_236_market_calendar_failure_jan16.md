# LL-236: CTO Did Not Check Market Calendar (Jan 16, 2026)

**Date**: 2026-01-16
**Category**: Compliance Failure
**Severity**: HIGH

## Failure

Scheduled workflow for Saturday January 17, 2026.
Markets are closed Saturday, Sunday, and Monday (MLK Day).

Next trading day: **Tuesday January 20, 2026**

## Root Cause

Did not verify market calendar before scheduling trades.

## Fix Applied

Rescheduled to Tuesday January 20, 9:35 AM ET.
Commit: bd421026f7f6a5319b9b4415ed3f06af26fdb3ff

## Prevention

Always check market calendar before scheduling any trade workflow.
Use Alpaca clock API or hardcoded holiday list.

## Tags

`failure`, `calendar`, `scheduling`
