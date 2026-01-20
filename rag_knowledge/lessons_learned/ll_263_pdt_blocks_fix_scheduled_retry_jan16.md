# LL-263: PDT Protection Blocks Spread Fix - Automated Retry Scheduled

**Date**: 2026-01-16 14:40 ET
**Category**: Constraint, Risk Management
**Severity**: MEDIUM

## Summary

The fix_653_spread.py script works correctly but PDT (Pattern Day Trading) protection is blocking execution.

## What Happened

1. Script correctly identified SPY260220P00653000 with qty=2
2. Script attempted to SELL 1 contract to balance the spread
3. Alpaca returned: "trade denied due to pattern day trading protection"

## PDT Rule Explanation

- Accounts under $25,000 cannot make 4+ day trades in 5 business days
- A "day trade" is buying AND selling the same security on the same day
- The earlier close attempts today triggered PDT protection
- This is a FINRA regulation, not an Alpaca-specific rule

## Current Account Status

- Equity: ~$4,977
- PDT threshold: $25,000
- Gap: ~$20,000

## Automated Resolution

Created scheduled workflow: `scheduled-fix-653-spread.yml`
- Runs tomorrow (Jan 17, 2026) at 9:35 AM ET
- Will automatically attempt to fix the spread
- If PDT still blocks, will log and retry next day

## No Manual Work Required

The system will automatically:
1. Retry the fix tomorrow morning
2. Log results to GitHub Actions
3. If successful, the spread will be balanced

## Prevention

To avoid PDT issues in future:
1. Limit day trades to 3 per 5-day window
2. Use swing trades (hold overnight) when possible
3. Size positions correctly so emergency closes are rare

## Phil Town Alignment

This constraint actually aligns with Rule #1 thinking:
- PDT forces us to think before trading
- Prevents impulsive day trading
- Encourages longer-term holding

## Tags
pdt, constraint, regulatory, automated-retry

