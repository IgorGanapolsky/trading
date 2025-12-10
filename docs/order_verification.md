# Order Verification System

## Overview

The order verification system is our "trust but verify" layer that validates local trade logs against Alpaca's actual order data. This is a critical component of the Anti-Lying Mandate - we never trust our own logs until they're verified against the ground truth (Alpaca API).

## Script: `scripts/verify_orders.py`

### Purpose

Verifies that:
1. Every order we logged actually exists in Alpaca
2. Order statuses match reality (filled, rejected, cancelled, etc.)
3. Filled quantities match expectations
4. Fill prices are within acceptable slippage limits

### Exit Codes

- **0**: All orders verified successfully
- **1**: Critical issues found (missing orders, excessive slippage, rejections)

### GitHub Actions Integration

The script writes to `GITHUB_OUTPUT` for CI/CD workflows:

```bash
orders_verified=true/false
orders_filled=N
orders_rejected=N
orders_missing=N
orders_slippage_errors=N
```

### Slippage Thresholds

- **Warning**: 1% - Logged but not critical
- **Error**: 2% - Fails verification, triggers investigation

### Usage

```bash
# Basic usage (requires .env with ALPACA_API_KEY and ALPACA_SECRET_KEY)
python3 scripts/verify_orders.py

# In CI/CD pipeline
python3 scripts/verify_orders.py
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
  echo "❌ Order verification failed"
  exit 1
fi
```

### Requirements

- Python 3.11+
- `alpaca-py>=0.43.2` (run `pip install -r requirements.txt`)
- Environment variables:
  - `ALPACA_API_KEY`
  - `ALPACA_SECRET_KEY`
  - `PAPER_TRADING` (default: true)

## Trade Log Format

### Required Fields

For verification to work, trade logs must include:

```json
{
  "symbol": "SPY",
  "action": "BUY",
  "amount": 10.0,
  "quantity": 0.022,
  "price": 450.00,
  "status": "FILLED",
  "order_id": "abc123-def456-ghi789",
  "timestamp": "2025-12-08T10:00:00"
}
```

### Field Descriptions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `symbol` | string | Yes | Stock/crypto symbol |
| `action` | string | Yes | BUY or SELL |
| `amount` | float | Yes | Dollar amount |
| `quantity` | float | Yes | Shares/units traded |
| `price` | float | Yes | Execution price |
| `status` | string | Yes | FILLED, REJECTED, etc. |
| `order_id` | string | **YES** | Alpaca order ID (for verification) |
| `timestamp` | string | Yes | ISO format timestamp |

### Important Notes

- **Analysis Mode**: Trades logged in "ANALYSIS" mode (paper trading simulations) won't have `order_id` and can't be verified
- **Real Trades**: All actual Alpaca orders MUST include `order_id`
- **Missing order_id**: Script will warn but not fail (allows for analysis mode trades)

## Implementation in Code

### Crypto Strategy (Example)

```python
# From src/strategies/crypto_strategy.py
def _save_trade_to_daily_file(
    self,
    symbol: str,
    action: str,
    amount: float,
    quantity: float,
    price: float,
    order_id: str,  # ← REQUIRED for verification
    data_dir: Path = Path("data"),
) -> None:
    trade_data = {
        "symbol": symbol,
        "action": action,
        "amount": round(amount, 2),
        "quantity": quantity,
        "price": round(price, 2),
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "status": "FILLED",
        "strategy": "CryptoStrategy",
        "order_id": order_id,  # ← Saved for later verification
    }
    # Save to data/trades_YYYY-MM-DD.json
```

### After Order Execution

```python
# Execute order via Alpaca
executed_order = self.trader.execute_order(
    symbol=symbol,
    amount_usd=amount,
    side="buy"
)

# CRITICAL: Save with order_id for verification
self._save_trade_to_daily_file(
    symbol=symbol,
    action="BUY",
    amount=amount,
    quantity=quantity,
    price=current_price,
    order_id=executed_order.get("id", ""),  # ← Get order ID from Alpaca response
)
```

## CI/CD Integration

### GitHub Actions Workflow

```yaml
name: Verify Orders

on:
  schedule:
    - cron: '0 16 * * 1-5'  # 4 PM ET weekdays (after trading)
  workflow_dispatch:

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Verify Orders
        env:
          ALPACA_API_KEY: ${{ secrets.ALPACA_API_KEY }}
          ALPACA_SECRET_KEY: ${{ secrets.ALPACA_SECRET_KEY }}
          PAPER_TRADING: true
        run: |
          python3 scripts/verify_orders.py

      - name: Check Results
        if: always()
        run: |
          if [ -f $GITHUB_OUTPUT ]; then
            cat $GITHUB_OUTPUT
          fi

      - name: Alert on Failure
        if: failure()
        uses: actions/github-script@v7
        with:
          script: |
            github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: '🚨 Order Verification Failed',
              body: 'Order verification detected discrepancies. Check workflow logs for details.',
              labels: ['trading', 'verification', 'urgent']
            })
```

## Verification Results

### Successful Verification

```
================================================================================
📋 ORDER VERIFICATION REPORT - Trust but Verify
================================================================================

📅 Date: 2025-12-08 04:00:00 PM
🌐 Mode: Paper Trading

📖 Loading local trade logs...
   Found 3 logged trades

🌐 Connecting to Alpaca API...
📥 Fetching orders from Alpaca...
   Found 3 orders in Alpaca

────────────────────────────────────────────────────────────────────────────────
🔍 VERIFICATION RESULTS
────────────────────────────────────────────────────────────────────────────────

[1/3] SPY - BUY
  ✅ Order found in Alpaca (ID: abc123)
  📊 Status: filled
  💰 Slippage: +0.05% ($0.0012)
  ✅ All checks passed

[2/3] QQQ - BUY
  ✅ Order found in Alpaca (ID: def456)
  📊 Status: filled
  💰 Slippage: -0.03% ($-0.0008)
  ✅ All checks passed

[3/3] BTCUSD - BUY
  ✅ Order found in Alpaca (ID: ghi789)
  📊 Status: filled
  💰 Slippage: +0.12% ($0.0089)
  ✅ All checks passed

────────────────────────────────────────────────────────────────────────────────
📊 SUMMARY
────────────────────────────────────────────────────────────────────────────────

Total trades logged:     3
✅ Verified:             3
📈 Filled:               3
❌ Rejected/Cancelled:   0
🔍 Missing from Alpaca:  0
⚠️  Slippage errors:      0

✅ VERIFICATION PASSED
   All orders verified successfully against Alpaca API

================================================================================
```

### Failed Verification

```
[2/3] QQQ - BUY
  ❌ Order NOT FOUND in Alpaca
  ℹ️  Order order-id-456 NOT FOUND in Alpaca

[3/3] TSLA - BUY
  ✅ Order found in Alpaca (ID: ghi789)
  📊 Status: rejected
  🚨 CRITICAL: Slippage +2.5% exceeds 2.0% limit
  ⚠️  Order was REJECTED

────────────────────────────────────────────────────────────────────────────────
📊 SUMMARY
────────────────────────────────────────────────────────────────────────────────

Total trades logged:     3
✅ Verified:             1
📈 Filled:               1
❌ Rejected/Cancelled:   1
🔍 Missing from Alpaca:  1
⚠️  Slippage errors:      1

❌ VERIFICATION FAILED
   1 orders missing from Alpaca
   1 orders with excessive slippage
   1 orders rejected/cancelled

================================================================================
```

## Troubleshooting

### Issue: "No order_id in local log"

**Cause**: Trade was logged without Alpaca order ID (likely analysis mode)

**Solution**:
- For real trades, ensure `order_id` is saved from Alpaca response
- For analysis mode, this is expected and can be ignored

### Issue: "Order NOT FOUND in Alpaca"

**Cause**: Local log has order_id that doesn't exist in Alpaca

**Possible Reasons**:
1. Order was placed on different day (check date)
2. Order ID was corrupted/incorrect in log
3. Using wrong Alpaca account (paper vs live)
4. Bug in trade logging system

**Solution**:
1. Check order date matches verification date
2. Verify PAPER_TRADING env var matches logged trades
3. Manually check Alpaca dashboard for order
4. Review trade logging code for bugs

### Issue: "Excessive Slippage"

**Cause**: Fill price differs from expected price by >2%

**Possible Reasons**:
1. Market volatility during execution
2. Low liquidity symbol
3. Large order size relative to volume
4. Technical issue with price data

**Solution**:
1. Review market conditions at execution time
2. Consider using limit orders for better price control
3. Verify price data source is accurate
4. Check for execution bugs

## Anti-Lying Mandate Compliance

This verification system ensures compliance with the Anti-Lying Mandate:

✅ **Ground Truth Source**: Always uses Alpaca API as source of truth
✅ **No Assumptions**: Never assumes order status - always verifies
✅ **Full Disclosure**: Reports ALL discrepancies clearly
✅ **CI Integration**: Fails builds on verification errors
✅ **Transparent Results**: Color-coded output shows exactly what passed/failed

**Remember**: Local logs are UNVERIFIED until proven correct against Alpaca API.

## Future Enhancements

1. **Historical Verification**: Verify all past trades, not just today's
2. **Reconciliation**: Auto-correct local logs based on Alpaca data
3. **Slack Alerts**: Send alerts on verification failures
4. **Trend Analysis**: Track slippage trends over time
5. **Performance Metrics**: Calculate actual vs expected execution quality

## Related Documentation

- [Anti-Lying Mandate](./verification-protocols.md)
- [Trade Execution](./README_COMPREHENSIVE.md#trade-execution)
- [Alpaca Integration](./ALPACA_ANALYSIS.md)
- [CI/CD Workflows](../.github/workflows/README.md)
