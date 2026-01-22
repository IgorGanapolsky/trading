# LL-292: Alpaca API Treats Close as Open for Options

**Date**: January 22, 2026
**Severity**: CRITICAL
**Category**: Broker API Bug

## Summary

When attempting to SELL to close a LONG put option position, Alpaca's API treats the order as OPENING a new SHORT put position, requiring massive margin that isn't available.

## The Bug

```
Attempting to close: SELL 8x SPY260220P00658000 (LONG puts)

Response Code: 403
Message: "insufficient options buying power for cash-secured put
         (required: 113000, available: 2607.46)"
```

**What happens:**
1. We own LONG 8x SPY260220P00658000 puts
2. We submit SELL order to close position
3. Alpaca calculates margin as if we're OPENING 8 SHORT puts
4. 8 contracts x $658 strike x 100 shares x ~17% margin = ~$113,000 required
5. We only have $2,607 buying power
6. Order rejected with 403

## What We Tried (All Failed)

| Method | Result |
|--------|--------|
| `DELETE /v2/positions/{symbol}` | 403 - insufficient buying power |
| `POST /v2/orders` (market sell) | 403 - insufficient buying power |
| Set `pdt_check="entry"` then close | Still 403 - not PDT, it's margin |
| `close_position()` via alpaca-py | 403 - same error |

## Root Cause

Alpaca's options API doesn't properly recognize that selling an existing LONG position is a CLOSING trade, not an OPENING trade. It calculates margin requirements as if opening a new short position.

This is likely related to:
- `closing_transactions_only: true` setting
- Options-specific margin calculations
- Possible bug in position netting logic

## Impact

- 18 contracts stuck, cannot close via API
- -$596 unrealized loss at time of discovery
- Positions will remain until Feb 20, 2026 expiration

## Workarounds

1. **Reset paper account** - Clears all positions (requires web interface)
2. **Wait for expiration** - Feb 20, 2026
3. **Contact Alpaca support** - Request manual close
4. **Alpaca auto-liquidation** - If ITM at 3:30 PM on expiration day

## Prevention

1. **Use $25K+ accounts** - Avoids PDT, but this bug is margin-related not PDT
2. **Trade smaller positions** - Less margin requirement if bug occurs
3. **Test close orders in sandbox first** - Before live trading
4. **Monitor for Alpaca API updates** - Bug may be fixed

## References

- [Alpaca Forum - Unable to Close Positions](https://forum.alpaca.markets/t/unable-to-close-positions/6024)
- [Alpaca Options Trading Overview](https://docs.alpaca.markets/docs/options-trading-overview)
- Diagnostic workflow run: https://github.com/IgorGanapolsky/trading/actions/runs/21264161084

## Related Lessons

- LL-290: Position Accumulation Bug
- LL-291: CTO Three-Day Crisis
- LL-272: SOFI Position Blocked All Trading
