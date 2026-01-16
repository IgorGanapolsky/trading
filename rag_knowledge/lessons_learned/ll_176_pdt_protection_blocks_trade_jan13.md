# LL-176: Lesson ll_176: Pattern Day Trading (PDT) Protection Blocked Trade

**Date:** January 13, 2026
**Category:** Regulatory Compliance
**Severity:** CRITICAL

## What Happened
Attempted to close a profitable short put position (+$5 unrealized P/L) to lock in gains per Phil Town Rule #1. Order was rejected by Alpaca with:
```
APIError: {"code":40310100,"message":"trade denied due to pattern day trading protection"}
```

## Root Cause
Account equity is $4,989.45, which is below the $25,000 PDT threshold. SEC regulations limit accounts under $25K to 3 day trades per 5 business days.

## Impact
- Cannot close winning position same-day to lock in profits
- Forced to hold position overnight, risking gains
- Rule #1 compliance is IMPOSSIBLE with PDT restrictions on small accounts

## Prevention
1. **Track day trade count** - Add tracking of day trades used (3 per 5 days)
2. **Multi-day holding strategy** - With $5K account, hold positions at least overnight to avoid PDT
3. **Account size priority** - Growing to $25K+ removes PDT restriction
4. **Position entry timing** - Enter positions knowing you cannot exit same-day

## Key Insight
With a sub-$25K account, Phil Town Rule #1 cannot be fully implemented via same-day closing. Strategy must account for overnight risk until account reaches $25K.

## Tags
pdt, regulatory, alpaca, options, rule_one, account_size
