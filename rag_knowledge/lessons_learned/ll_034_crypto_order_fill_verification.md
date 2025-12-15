# LL-034: Always Verify Crypto Order Fills

**Date**: 2025-12-14
**Category**: Trading Execution
**Severity**: HIGH - Revenue Impact

## The Bug

Crypto orders were logged with `status: OrderStatus.PENDING_NEW` immediately after submission, without waiting for fill confirmation. The system reported trades as executed when they were only submitted.

## Impact

- Crypto P/L tracking was inaccurate
- Orders stuck in PENDING_NEW state were not detected
- System showed trades that may not have filled
- ~$96 unrealized loss went untracked

## Root Cause

In GitHub Actions workflows (`weekend-crypto-trading.yml`, `force-crypto-trade.yml`):

```python
# BAD - Saves immediately without waiting for fill
order = client.submit_order(MarketOrderRequest(...))
result["status"] = str(order.status)  # PENDING_NEW
save()  # Saves before fill!
```

## The Fix

Wait for order fill with timeout before logging:

```python
# GOOD - Wait for fill confirmation
order = client.submit_order(MarketOrderRequest(...))

# Wait for fill (up to 30 seconds for crypto)
import time
fill_timeout = 30
start = time.time()
filled_price = None

while time.time() - start < fill_timeout:
    order = client.get_order_by_id(order.id)
    if str(order.status) == "OrderStatus.FILLED":
        filled_price = float(order.filled_avg_price)
        break
    elif str(order.status) in ["OrderStatus.CANCELLED", "OrderStatus.REJECTED"]:
        break
    time.sleep(2)

result["status"] = str(order.status)  # Now shows FILLED
result["filled_price"] = filled_price
result["verified_fill"] = str(order.status) == "OrderStatus.FILLED"
save()
```

## Prevention Rules

1. **Never log trade as executed before fill confirmation**
2. **Always include `verified_fill` boolean in trade records**
3. **Store `filled_price` separately from estimated price**
4. **Use 30-second timeout for crypto (GTC orders fill quickly)**
5. **Log final status, not initial status**

## Related Files

- `.github/workflows/weekend-crypto-trading.yml`
- `.github/workflows/force-crypto-trade.yml`
- `src/strategies/crypto_strategy.py`
- `src/core/alpaca_trader.py`

## Tradier Note

Tradier CANNOT be used as a crypto backup - it only supports equities and options. For crypto redundancy, consider:
- Coinbase Pro API
- Kraken API
- Binance.US API

## RAG Query Patterns

- "crypto order not filling"
- "PENDING_NEW status"
- "verify trade fill"
- "crypto trade execution"
- "Alpaca crypto order"
