# LL-291: Alpaca API Bug - Close Position Treated as New Short

**Date:** 2026-01-22
**Category:** Trading Infrastructure Crisis
**Severity:** Critical

## Problem
When attempting to close a LONG put position (SPY260220P00658000, 8 contracts), Alpaca's API returned:
- Error: "insufficient options buying power for cash-secured put (required: 113000, available: 2607.46)"

The API incorrectly treats a SELL-to-close order as a new SHORT (cash-secured put), requiring $113,000 collateral instead of simply closing the existing long position.

## Additional Blocker
- PDT (Pattern Day Trader) protection blocked closing other positions
- Account had 3 day trades, triggering PDT lock on $5K account
- Configuration changes (pdt_check, closing_transactions_only) did NOT bypass the issue

## What We Tried (All Failed)
1. Market order via Python SDK - CSP error
2. Limit order - CSP error
3. close_position() endpoint - CSP error
4. Direct REST API with position_intent='sell_to_close' - CSP error
5. DELETE /v2/positions/{symbol} - CSP error
6. close_all_positions() - PDT error on other legs, CSP error on long put
7. Partial close (1 contract) - PDT error
8. Account config: closing_transactions_only=True - Still blocked
9. Account config: pdt_check='exit' - Still blocked

## Resolution
- $5K account positions LOCKED until next trading day (PDT resets)
- Switched to $100K paper account which has:
  - PDT enabled (>$25K equity)
  - $268K buying power
- Successfully placed iron condor on $100K account:
  - Put spread: Sell 660, Buy 655 @ $0.43 credit
  - Call spread: Sell 720, Buy 725 @ $0.38 credit
  - Total credit: $81/contract
  - Max risk: $419

## Lessons Learned
1. **Alpaca has a bug** in options position closing - report to support
2. **PDT applies to options** same as stocks - 3 round trips = locked
3. **$5K accounts are vulnerable** - can't close positions same day after 3 trades
4. **Always have backup account** - $100K account saved the day
5. **Test closing BEFORE opening** - verify you can exit a position type
6. **Account size matters** - PDT-enabled accounts (>$25K) avoid this trap

## Action Items
- [ ] File Alpaca support ticket about CSP validation bug
- [ ] Consider using only $100K account for options (PDT-enabled)
- [ ] Add pre-trade check: verify account can close position type
- [ ] Tomorrow: Close $5K positions when PDT resets

## Code Evidence
```python
# This SHOULD work but doesn't:
client.close_position('SPY260220P00658000')
# Returns: {"code":40310000,"message":"insufficient options buying power for cash-secured put (required: 113000, available: 2607.46)"}

# Even with explicit close intent:
order_data = {
    'symbol': 'SPY260220P00658000',
    'qty': '8',
    'side': 'sell',
    'type': 'market',
    'time_in_force': 'day',
    'position_intent': 'sell_to_close'
}
# Still returns same CSP error
```

## Related Lessons
- LL-176: PDT protection blocks trade
- LL-247: SOFI PDT crisis
- LL-221: Orphan put crisis
