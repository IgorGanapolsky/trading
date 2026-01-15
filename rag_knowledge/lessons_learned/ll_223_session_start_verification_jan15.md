# Lesson Learned: Session Start Verification Protocol

**ID**: LL-223
**Date**: January 15, 2026
**Severity**: HIGH
**Category**: Process / Data Integrity

## CEO Directive

"Every time I start a session, report exactly how much money we made today or lost today (with brief reasons). Report what is showing on the progress dashboard and GitHub - is it matching what Alpaca shows? Alpaca is the single source of truth. Query Dialogflow and verify it matches Alpaca."

## Solution Implemented

Created `scripts/session_start_verification.py` that:

1. **Fetches Alpaca API** (source of truth) - equity, P/L, positions
2. **Reads local cache** (system_state.json) - for comparison
3. **Fetches GitHub Pages** dashboard - for comparison
4. **Queries Dialogflow** - for AI assistant verification
5. **Reports discrepancies** - flags any mismatches

## Standard Session Start Procedure

When asked "How much money did we make today?":

1. Run: `python3 scripts/session_start_verification.py`
2. Report Alpaca data as source of truth
3. Flag any discrepancies with local cache or dashboard
4. Trigger sync workflow if data is stale

## Files Changed

- `scripts/session_start_verification.py` - New verification script
- `.claude/hooks/inject_trading_context.sh` - Added verification reminder

## Sandbox Limitation

In web sandbox environments, Alpaca API credentials are not available. The script gracefully handles this and reports based on cached data with a warning.

## Key Metrics to Report

1. **Today's P/L**: Change from yesterday's close
2. **Total P/L**: Change from initial $5,000
3. **Positions**: Current open positions
4. **Discrepancies**: Any mismatch between sources
