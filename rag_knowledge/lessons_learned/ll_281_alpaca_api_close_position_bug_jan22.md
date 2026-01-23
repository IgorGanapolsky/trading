# LL-281: Alpaca API Bug - Close Position Treated as Opening Cash-Secured Put

**ID**: LL-281
**Date**: 2026-01-22
**Severity**: CRITICAL
**Category**: Broker API, Position Management, Emergency

## Incident Summary

On Jan 22, 2026, all attempts to close SPY260220P00658000 (8 long put contracts, -$1,400 loss) via Alpaca API failed due to a broker-side bug.

## The Bug

When attempting to SELL TO CLOSE a LONG put position, Alpaca API treats it as OPENING a new short position (cash-secured put), requiring $113,000 buying power:

```
Error: {"code":40310000,"message":"insufficient options buying power for cash-secured put (required: 113000, available: 1313.22)"}
```

### Why This Is Wrong
- We are CLOSING an existing LONG position (SELL to close)
- Alpaca interprets it as OPENING a new SHORT position
- A short put at $658 strike would require collateral, but we're NOT opening one
- The API should recognize the existing long position and reduce/close it

## Attempted Workarounds (All Failed)

1. **Market order**: Same error
2. **Limit order at 95% price**: Same error
3. **Limit order at $0.01**: Same error
4. **Close just 1 contract**: PDT restriction blocked
5. **close_position() DELETE endpoint**: Same error (tested Jan 22, 17:03 UTC)
6. **Partial close via ClosePositionRequest**: Wrong API syntax + same underlying bug

## PDT Lock Status (Jan 22, 2026)

The account is **fully PDT-locked** today:
- SPY260220P00658000: Blocked by API bug ("insufficient options buying power")
- All other positions: Blocked by "trade denied due to pattern day trading protection"

**Portfolio Status:**
- Equity: ~$4,231
- Total unrealized P/L: -$1,341.33
- All 5 positions locked until Jan 23

## Contributing Factors

1. **PDT Restriction**: Account under $25K limits day trades
2. **Position opened same day**: Any close attempt counts as day trade
3. **Alpaca API bug**: Misclassifying close as open

## Resolution

**MANUAL ACTION REQUIRED** - CEO must close position directly via:
1. Alpaca Dashboard: https://app.alpaca.markets/paper/dashboard/positions
2. Click on SPY260220P00658000 position
3. Click "Close Position" button
4. The dashboard may bypass the API bug

**Alternative**: Wait until next trading day (Jan 23) when:
- Position will not be a day trade
- May bypass PDT restriction
- API bug may not trigger for non-same-day positions

## Prevention

1. Never accumulate positions beyond limits (LL-280 fix addresses this)
2. Always have emergency manual close procedures documented
3. Report Alpaca API bugs to their support

## Alpaca Support Ticket

Should file ticket with:
- Account: Paper trading $5K
- Symbol: SPY260220P00658000
- Action: SELL to close 8 long contracts
- Error: "insufficient options buying power for cash-secured put"
- Expected: Position should close, not require $113K collateral

## Resolution (Jan 22, 2026 - RESOLVED)

**Account was reset** - CEO created new $30K paper trading account (PA3PYE0C9MN):
- Old stuck positions abandoned (couldn't close via API)
- Fresh start with clean slate - 0 positions
- New account > $25K = NO PDT RESTRICTIONS
- All workflows updated to use new credentials (PR #2723)

**Lesson Applied**: Document Alpaca API bugs for future reference. If stuck again, reset account.

## Tags
`resolved`, `alpaca-api`, `broker-bug`, `position-close`, `pdt`, `account-reset`
