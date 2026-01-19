# LL-241: Hook Hallucinated "Markets OPEN" on MLK Day

**Date**: 2026-01-19
**Category**: System Bug, Hallucination
**Severity**: HIGH

## Problem

The `inject_trading_context.sh` hook reported "Markets: OPEN" on Martin Luther King Jr. Day (Jan 19, 2026) when markets were actually **CLOSED**.

## Root Cause

The hook only checked:
1. Weekday vs Weekend (Mon-Fri vs Sat-Sun)
2. Time of day (9:30 AM - 4:00 PM ET)

But **NEVER checked for federal market holidays**.

## Impact

- CEO was given incorrect information
- Could have led to trade attempts on closed market
- Violated "never lie" directive
- Damaged trust in system information

## Fix Applied

Added hardcoded 2026 NYSE/NASDAQ holiday list to hook:
- Jan 1: New Year's Day
- Jan 19: MLK Day
- Feb 16: Presidents' Day
- Apr 3: Good Friday
- May 25: Memorial Day
- Jun 19: Juneteenth
- Jul 3: Independence Day (observed)
- Sep 7: Labor Day
- Nov 26: Thanksgiving
- Dec 25: Christmas

Now returns: `Markets: HOLIDAY_CLOSED - [Holiday Name] - Markets closed all day`

## Remaining Gaps

Other workflows that run on `1-5` (weekdays) but lack holiday checks:
- `daily-trading.yml`
- `cancel-stale-orders.yml`
- `sync-alpaca-status.yml`
- `phil-town-ingestion.yml`

Only `execute-credit-spread.yml` has proper Alpaca calendar validation.

## Prevention

1. Add calendar validation to all trading-critical workflows
2. Update holiday list annually (add 2027 holidays in late 2026)
3. Consider using Alpaca API for dynamic holiday detection in hook

## Phil Town Rule 1 Impact

Incorrect market status could lead to:
- Attempted trades during closed markets
- Missed opportunities on actual trading days
- System appearing unreliable

## Tags
`hooks`, `hallucination`, `market-status`, `holiday`, `critical-bug`
