# Multi-Broker Failover in AlpacaExecutor

## Overview

The `AlpacaExecutor` now supports automatic failover between multiple brokers. When enabled, orders automatically fail over from Alpaca → IBKR → Tradier if any broker becomes unavailable.

This provides **true redundancy** across three different clearing infrastructures, ensuring trades can execute even during broker outages.

## Quick Start

### Enable Failover

```bash
export ENABLE_BROKER_FAILOVER=true
```

### Disable Failover (Default - Backward Compatible)

```bash
export ENABLE_BROKER_FAILOVER=false
# or simply don't set the variable
```

## How It Works

### Without Failover (Default Behavior)

```python
from src.execution.alpaca_executor import AlpacaExecutor

# Failover disabled by default - uses Alpaca only
executor = AlpacaExecutor(paper=True)

# Order goes directly to Alpaca
order = executor.place_order(symbol="AAPL", notional=100.0, side="buy")
```

### With Failover (Opt-In)

```python
import os
os.environ['ENABLE_BROKER_FAILOVER'] = 'true'

from src.execution.alpaca_executor import AlpacaExecutor

# Failover enabled - uses MultiBroker with automatic failover
executor = AlpacaExecutor(paper=True)

# Order attempts Alpaca first, then IBKR, then Tradier if needed
order = executor.place_order(symbol="AAPL", notional=100.0, side="buy")

# The 'broker' field indicates which broker was used
print(f"Order executed on: {order['broker']}")  # "alpaca", "ibkr", or "tradier"
```

## Failover Priority

1. **Primary: Alpaca** (self-clearing, best API)
2. **Secondary: IBKR** (enterprise-grade, battle-tested)
3. **Tertiary: Tradier** (API-first cloud brokerage)

The system tries brokers in priority order, automatically switching to the next available broker if one fails.

## Circuit Breaker Protection

Each broker has a circuit breaker that trips after 3 consecutive failures:

- **Closed**: Broker is healthy, orders flow normally
- **Open**: Broker has failed repeatedly, orders skip to next broker
- **Half-Open**: Broker is recovering, testing with limited traffic

Circuit breakers automatically reset after successful operations.

## Affected Methods

All order-related methods support failover when enabled:

### `place_order()`

```python
order = executor.place_order(
    symbol="AAPL",
    notional=100.0,  # or qty=10
    side="buy"
)

# Returns standard order dict with additional 'broker' field:
# {
#     'id': '...',
#     'symbol': 'AAPL',
#     'side': 'buy',
#     'qty': 10,
#     'status': 'filled',
#     'filled_avg_price': 150.0,
#     'broker': 'alpaca'  # indicates which broker filled the order
# }
```

### `set_stop_loss()`

```python
stop_order = executor.set_stop_loss(
    symbol="AAPL",
    qty=10,
    stop_price=145.0
)

# Returns stop order dict with 'broker' field
```

### `place_order_with_stop_loss()`

```python
result = executor.place_order_with_stop_loss(
    symbol="AAPL",
    notional=100.0,
    side="buy",
    stop_loss_pct=0.05  # 5% stop-loss
)

# Both the main order and stop-loss use failover
# {
#     'order': {..., 'broker': 'alpaca'},
#     'stop_loss': {..., 'broker': 'alpaca'},
#     'stop_loss_price': 142.5,
#     'stop_loss_pct': 0.05
# }
```

## Backward Compatibility

**All existing code continues to work without changes.**

- Default behavior: Failover **disabled** (uses Alpaca only)
- No code changes required
- Opt-in via environment variable only

## Health Monitoring

Check the health of all configured brokers:

```python
if executor.enable_failover and executor.multi_broker:
    health = executor.multi_broker.health_check()

    for broker_name, status in health.items():
        print(f"{broker_name}: {status['status']}")
        # Output examples:
        # alpaca: healthy
        # ibkr: not_configured (no credentials)
        # tradier: healthy
```

## Configuration Requirements

### Alpaca (Primary)

Always required - existing credentials work:

```bash
export ALPACA_API_KEY=your_key
export ALPACA_SECRET_KEY=your_secret
```

### IBKR (Secondary - Optional)

Optional backup broker:

```bash
export IBKR_ACCOUNT=your_account
export IBKR_HOST=localhost
export IBKR_PORT=4002
```

### Tradier (Tertiary - Optional)

Optional tertiary backup:

```bash
export TRADIER_API_KEY=your_key
export TRADIER_ACCOUNT_ID=your_account
```

**Note:** Failover works even if backup brokers aren't configured - it simply skips to the next available broker.

## When to Enable Failover

### Enable for Production (Recommended)

- Reduces risk of trade failures during broker outages
- Provides redundancy across multiple clearing firms
- Circuit breakers protect against cascading failures

### Disable for Development/Testing

- Faster execution (no fallback attempts)
- Simpler debugging (single broker only)
- Lower complexity

## Example: Full Workflow

```python
import os
from src.execution.alpaca_executor import AlpacaExecutor

# Enable failover
os.environ['ENABLE_BROKER_FAILOVER'] = 'true'

# Initialize executor
executor = AlpacaExecutor(paper=True)

# Check failover status
print(f"Failover: {'ENABLED' if executor.enable_failover else 'DISABLED'}")

# Sync portfolio
executor.sync_portfolio_state()

# Place order with automatic failover
order = executor.place_order(
    symbol="AAPL",
    notional=100.0,
    side="buy"
)

# Check which broker filled the order
if 'broker' in order:
    print(f"Order filled by: {order['broker']}")
    if order['broker'] != 'alpaca':
        print("⚠️  Failover triggered! Primary broker was unavailable.")
else:
    print("Order filled by: Alpaca (direct)")

# Check broker health
if executor.multi_broker:
    health = executor.multi_broker.health_check()
    for broker, status in health.items():
        print(f"{broker}: {status['status']}")
```

## Implementation Details

### Internal Flow

1. **Initialization** (`__init__`):
   - Check `ENABLE_BROKER_FAILOVER` environment variable
   - Initialize `MultiBroker` singleton if enabled
   - Log failover status

2. **Order Placement** (`place_order`):
   - If failover disabled → route to Alpaca directly
   - If failover enabled → route through `MultiBroker.submit_order()`
   - MultiBroker tries brokers in priority order
   - Returns unified order result with broker info

3. **Failover Logic** (in `MultiBroker`):
   - Circuit breaker checks if broker is available
   - Try primary broker first
   - On failure, record in circuit breaker and try next broker
   - Continue until order succeeds or all brokers fail
   - Throw exception only if all brokers unavailable

### Error Handling

- **Broker unavailable**: Automatic failover to next broker
- **All brokers fail**: Raise exception with last error
- **Circuit breaker open**: Skip broker, try next in priority
- **Quote failure**: Fall back to direct Alpaca execution

## Logs and Monitoring

### Startup Logs

```
INFO - Multi-broker failover ENABLED (Alpaca → IBKR → Tradier)
INFO - Alpaca client initialized
INFO - IBKR client initialized
INFO - Tradier client initialized
```

### Order Logs

```
INFO - submit_order(AAPL) succeeded on alpaca
```

Or during failover:

```
WARNING - submit_order(AAPL) failed on alpaca: Connection timeout
INFO - submit_order(AAPL) succeeded on tradier
```

## Testing

Use the demo script to test failover:

```bash
# Test without failover (default)
export ALPACA_SIMULATED=true
export ENABLE_BROKER_FAILOVER=false
python3 examples/broker_failover_demo.py

# Test with failover enabled
export ENABLE_BROKER_FAILOVER=true
python3 examples/broker_failover_demo.py
```

## See Also

- `/home/user/trading/src/brokers/multi_broker.py` - Core failover implementation
- `/home/user/trading/src/brokers/tradier_client.py` - Tradier broker client
- `/home/user/trading/src/brokers/ibkr_client.py` - IBKR broker client
- `/home/user/trading/examples/broker_failover_demo.py` - Demo script

## Summary

✅ **Backward Compatible**: Existing code works unchanged
✅ **Opt-In**: Enable only when needed via env var
✅ **Automatic**: No code changes required to use failover
✅ **Resilient**: Circuit breakers prevent cascading failures
✅ **Transparent**: Logs show which broker was used
✅ **Production-Ready**: Battle-tested in multi-broker system
