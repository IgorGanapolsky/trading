# IV Data Provider API Reference

**Location**: `/home/user/trading/src/data/iv_data_provider.py`

**Author**: Claude (CTO)
**Created**: 2025-12-10
**Lines of Code**: 1,545

---

## Overview

The `IVDataProvider` class provides real-time and historical implied volatility (IV) data for options trading strategies. It integrates with Alpaca Options API, falls back to yfinance, and includes aggressive caching for performance.

---

## Quick Start

```python
from src.data.iv_data_provider import get_iv_data_provider

# Get singleton instance
provider = get_iv_data_provider()

# Fetch basic IV metrics
current_iv = provider.get_current_iv("SPY")
iv_rank = provider.get_iv_rank("AAPL")
iv_percentile = provider.get_iv_percentile("NVDA")
```

---

## Core Methods

### 1. **get_current_iv(ticker)**
Get current implied volatility for an underlying symbol.

```python
iv = provider.get_current_iv("SPY")
# Returns: 0.1234 (12.34% annualized)
```

**Returns**: `float` - Current IV as decimal

**Data Sources** (in priority order):
1. Alpaca Options API (direct IV from option chain)
2. Calculated IV from option prices
3. VIX proxy (last resort)

---

### 2. **get_iv_rank(ticker, lookback=252)**
Get IV Rank: where current IV sits in historical range.

```python
iv_rank = provider.get_iv_rank("AAPL", lookback=252)
# Returns: 65.5 (current IV is 65.5% of the way from min to max)
```

**Formula**: `(current_iv - 52w_low) / (52w_high - 52w_low) * 100`

**Parameters**:
- `ticker` (str): Stock symbol
- `lookback` (int): Days to look back (default 252 = 1 year)

**Returns**: `float` - IV Rank from 0-100

**Trading Signals**:
- **0-20**: VERY LOW - Buy premium (cheap options)
- **20-30**: LOW - Consider buying
- **30-50**: NEUTRAL - No clear edge
- **50-75**: HIGH - Sell premium
- **75-100**: VERY HIGH - Aggressive premium selling

---

### 3. **get_iv_percentile(ticker)**
Get IV Percentile: percentage of days in last year with lower IV.

```python
iv_percentile = provider.get_iv_percentile("TSLA")
# Returns: 70.0 (70% of days had lower IV)
```

**Returns**: `float` - IV Percentile from 0-100

**Difference from IV Rank**:
- **IV Rank**: Linear position in range (min to max)
- **IV Percentile**: % of days below current level (distribution-based)

---

### 4. **get_iv_skew(ticker)** ⭐ NEW
Get IV Skew: Put IV vs Call IV (fear vs greed indicator).

```python
skew = provider.get_iv_skew("SPY")
# Returns:
# {
#     "call_iv": 0.1200,
#     "put_iv": 0.1350,
#     "skew": 0.0150,
#     "skew_pct": 12.50,
#     "interpretation": "BEARISH - Strong put demand (fear)"
# }
```

**Interpretation**:
- **Positive skew** (puts > calls): Bearish sentiment, fear in market
- **Negative skew** (calls > puts): Bullish sentiment, greed in market
- **Neutral** (< 2% difference): Balanced market

**Use Cases**:
- Market sentiment gauge
- Contrarian signals (extreme fear = buy, extreme greed = sell)
- Options strategy selection (sell puts in high fear, sell calls in high greed)

---

### 5. **get_term_structure(ticker)** ⭐ NEW
Get IV Term Structure: IV across different expirations.

```python
term = provider.get_term_structure("AAPL")
# Returns:
# {
#     "expirations": ["2025-12-15", "2025-12-22", "2025-12-29"],
#     "ivs": [0.2100, 0.2250, 0.2400],
#     "structure_type": "normal",
#     "front_month_iv": 0.2100,
#     "back_month_iv": 0.2400,
#     "slope": 0.0150
# }
```

**Structure Types**:
- **normal**: Upward sloping (uncertainty increases with time)
- **inverted**: Downward sloping (near-term event risk - earnings, Fed meeting)
- **flat**: Minimal slope (consistent volatility expectations)
- **humped**: Peak in middle (specific mid-term event expected)

**Use Cases**:
- Calendar spreads (buy back month, sell front month in normal structure)
- Event detection (inverted = near-term catalyst)
- Expiration selection (choose based on term structure shape)

---

### 6. **get_options_chain_with_greeks(ticker, expiration, filters)** ⭐ NEW
Fetch full options chain with Greeks, filtered and sorted by liquidity.

```python
options = provider.get_options_chain_with_greeks(
    symbol="SPY",
    expiration="2025-12-20",  # Optional: None = all expirations
    min_delta=0.20,            # Optional: filter by delta range
    max_delta=0.40,
    min_volume=10,             # Optional: liquidity filters
    min_open_interest=50
)

# Returns: List of option contracts
# [
#     {
#         "symbol": "SPY251220C00600000",
#         "strike": 600.0,
#         "expiration": "2025-12-20",
#         "type": "call",
#         "bid": 2.50,
#         "ask": 2.55,
#         "last": 2.52,
#         "volume": 1500,
#         "open_interest": 5000,
#         "iv": 0.1234,
#         "delta": 0.30,
#         "gamma": 0.0123,
#         "theta": -0.05,
#         "vega": 0.15,
#         "rho": 0.08,
#         "liquidity_score": 11500  # volume + (OI * 2)
#     },
#     ...
# ]
```

**Parameters**:
- `symbol` (str): Stock symbol
- `expiration` (str, optional): Specific expiration (YYYY-MM-DD) or None for all
- `min_delta` (float, optional): Minimum absolute delta
- `max_delta` (float, optional): Maximum absolute delta
- `min_volume` (int): Minimum daily volume (default 0)
- `min_open_interest` (int): Minimum open interest (default 0)

**Returns**: `List[Dict]` - Options sorted by liquidity (highest first)

**Liquidity Score**: `volume + (open_interest * 2)`
- Open interest weighted 2x (more stable than daily volume)

---

### 7. **find_optimal_strikes(ticker, strategy, target_delta, expiration)** ⭐ NEW
Find optimal strike prices for specific options strategies.

```python
# Covered Call (0.30 delta OTM call)
result = provider.find_optimal_strikes("SPY", "covered_call")

# Returns:
# {
#     "strategy": "covered_call",
#     "symbol": "SPY",
#     "current_price": 580.50,
#     "expiration": "2025-12-20",
#     "contract": {
#         "symbol": "SPY251220C00590000",
#         "strike": 590.0,
#         "delta": 0.30,
#         "iv": 0.1234,
#         ...
#     },
#     "expected_credit": 2.50,
#     "max_profit": 12.00,  # (strike - current) + credit
#     "break_even": 578.00  # current - credit
# }
```

**Supported Strategies**:

| Strategy | Default Delta | Description |
|----------|--------------|-------------|
| `covered_call` | 0.30 | Sell OTM call against long stock |
| `cash_secured_put` | -0.30 | Sell OTM put (get paid to buy stock) |
| `credit_spread_call` | 0.30 | Bear call spread |
| `credit_spread_put` | -0.30 | Bull put spread |
| `iron_condor` | 0.16 | Wings (0.30 short strikes) |
| `protective_put` | -0.20 | Hedge long stock |

**Parameters**:
- `symbol` (str): Stock symbol
- `strategy` (str): Strategy type (see table above)
- `target_delta` (float, optional): Override default delta
- `expiration` (str, optional): Specific expiration or None for nearest

**Returns**: `Dict` with optimal strikes and P&L metrics

**Example Use Cases**:

```python
# 1. Weekly covered calls on SPY
cc = provider.find_optimal_strikes("SPY", "covered_call", expiration="2025-12-13")
print(f"Sell {cc['contract']['symbol']} for ${cc['expected_credit']:.2f} credit")

# 2. Iron condor on high IV stock
ic = provider.find_optimal_strikes("NVDA", "iron_condor")
print(f"Max profit: ${ic['max_profit']:.2f}, Max loss: ${ic['max_loss']:.2f}")

# 3. Custom delta protective put
pp = provider.find_optimal_strikes("TSLA", "protective_put", target_delta=0.15)
print(f"Protect below ${pp['protected_below']:.2f} for ${pp['cost']:.2f}")
```

---

### 8. **cache_iv_data(ticker, data)** ⭐ NEW
Manually cache IV data for a symbol.

```python
custom_data = {
    "current_iv": 0.25,
    "iv_rank": 65.0,
    "iv_percentile": 70.0,
    "data_source": "third_party_api",
    "confidence": 0.9
}
provider.cache_iv_data("AAPL", custom_data)
```

**Parameters**:
- `symbol` (str): Stock symbol
- `data` (dict): IV data to cache (see example above)

**Cache TTL**: 5 minutes (configurable via `IVDataProvider.IV_DATA_TTL`)

---

### 9. **load_cached_iv(ticker, max_age_minutes=5)** ⭐ NEW
Load cached IV data if fresh enough.

```python
cached = provider.load_cached_iv("AAPL", max_age_minutes=5)

if cached:
    print(f"Cached IV: {cached['current_iv']:.4f}")
    print(f"Cache age: < {max_age_minutes} minutes")
else:
    print("No fresh cache available")
```

**Parameters**:
- `symbol` (str): Stock symbol
- `max_age_minutes` (int): Maximum cache age in minutes (default 5)

**Returns**: `Dict | None` - Cached data if fresh, None otherwise

**Cache Storage**:
1. In-memory cache (fastest)
2. Disk cache at `data/cache/iv/{symbol}_metrics.json`

---

## Additional Methods

### get_full_metrics(ticker)
Get complete IV metrics as a structured object.

```python
metrics = provider.get_full_metrics("SPY")
print(metrics.current_iv)
print(metrics.iv_rank)
print(metrics.iv_percentile)
print(metrics.data_source)
print(metrics.confidence)
```

**Returns**: `IVMetrics` dataclass with all IV data

---

### get_vix()
Get current VIX level (market volatility proxy).

```python
vix = provider.get_vix()
# Returns: 15.5
```

**VIX Regimes**:
- **< 15**: LOW - Markets calm
- **15-20**: ELEVATED - Normal volatility
- **20-25**: HIGH - Increased volatility
- **25-30**: VERY HIGH - Market stress
- **> 30**: EXTREME - Crisis mode

---

### get_iv_history(ticker, days=252)
Get historical IV for a symbol.

```python
history = provider.get_iv_history("AAPL", days=30)
# Returns: [0.2100, 0.2050, 0.2150, ...]  # Most recent first
```

**Parameters**:
- `symbol` (str): Stock symbol
- `days` (int): Number of trading days (default 252 = 1 year)

**Returns**: `List[float]` - Daily IV values (most recent first)

---

### clear_cache(ticker=None)
Clear cached IV data.

```python
# Clear specific symbol
provider.clear_cache("AAPL")

# Clear all cache
provider.clear_cache()
```

---

## Caching Strategy

### Cache Levels

1. **In-Memory Cache** (fastest)
   - Duration: 5 minutes for IV data, 1 hour for IV rank
   - Survives: Current Python session only

2. **Disk Cache** (persistent)
   - Location: `data/cache/iv/{symbol}_metrics.json`
   - Duration: Same as in-memory
   - Survives: Across sessions

### Cache TTLs

```python
IVDataProvider.IV_DATA_TTL = 5 * 60      # 5 minutes
IVDataProvider.IV_RANK_TTL = 60 * 60     # 1 hour
IVDataProvider.VIX_TTL = 5 * 60          # 5 minutes
```

**Why These TTLs?**
- Options IV doesn't change tick-by-tick (5 min is sufficient)
- IV rank/percentile are historical metrics (1 hour is safe)
- VIX updates frequently but not critically (5 min balances cost/freshness)

---

## Data Sources

### Priority Hierarchy

1. **Alpaca Options API** (highest priority)
   - Direct IV from option chain
   - Confidence: 95%
   - Requires: `ALPACA_API_KEY`, `ALPACA_SECRET_KEY` environment variables

2. **Calculated IV from Option Prices** (fallback)
   - Uses Black-Scholes implied volatility solver
   - Confidence: 70-80%
   - Currently: Not implemented (placeholder)

3. **VIX Proxy** (last resort)
   - Scales VIX by beta and correlation
   - Confidence: 40%
   - Always available via yfinance

---

## Integration Examples

### Options IV Signal Generator

```python
from src.data.iv_data_provider import get_iv_data_provider

provider = get_iv_data_provider()

def get_options_signal(symbol):
    """Determine whether to buy or sell premium"""
    iv_rank = provider.get_iv_rank(symbol)

    if iv_rank > 75:
        return "SELL_PREMIUM", "Very high IV - sell options"
    elif iv_rank < 20:
        return "BUY_PREMIUM", "Very low IV - buy options"
    else:
        return "NEUTRAL", "IV in middle range"

signal, reason = get_options_signal("SPY")
print(f"{signal}: {reason}")
```

---

### Theta Harvest Executor

```python
from src.data.iv_data_provider import get_iv_data_provider

provider = get_iv_data_provider()

def should_harvest_theta(symbol):
    """Check if conditions are right for theta harvesting"""
    iv_rank = provider.get_iv_rank(symbol)
    skew = provider.get_iv_skew(symbol)

    # Ideal conditions:
    # 1. High IV (expensive premium)
    # 2. Bullish skew (expensive puts) for put selling

    if iv_rank > 60 and skew.get("skew_pct", 0) > 5:
        return True, "High IV + bearish skew = expensive puts"

    return False, "Not optimal for theta harvest"

should_trade, reason = should_harvest_theta("NVDA")
print(f"Trade: {should_trade} - {reason}")
```

---

### Covered Call Strike Selection

```python
from src.data.iv_data_provider import get_iv_data_provider

provider = get_iv_data_provider()

def select_covered_call_strike(symbol, shares_owned=100):
    """Find optimal covered call strike"""

    # Get optimal 0.30 delta call
    result = provider.find_optimal_strikes(symbol, "covered_call")

    if "error" in result:
        return None

    contract = result["contract"]

    print(f"\n{symbol} Covered Call:")
    print(f"  Own: {shares_owned} shares @ ${result['current_price']:.2f}")
    print(f"  Sell: 1 contract of {contract['symbol']}")
    print(f"  Strike: ${contract['strike']:.2f} ({contract['delta']:.3f} delta)")
    print(f"  Credit: ${result['expected_credit']:.2f} × 100 = ${result['expected_credit'] * 100:.2f}")
    print(f"  Max Profit: ${result['max_profit'] * 100:.2f}")
    print(f"  Probability of Profit: ~{(1 - abs(contract['delta'])) * 100:.1f}%")

    return result

select_covered_call_strike("SPY", shares_owned=100)
```

---

## Performance Considerations

### API Rate Limits

**Alpaca Options API**:
- 200 requests/minute for market data
- Each `get_option_chain()` call = 1 request
- Cache aggressively to stay under limits

### Optimization Tips

1. **Use caching** - Don't fetch same data repeatedly
2. **Batch symbols** - Process multiple symbols in one session
3. **Filter early** - Use delta/volume filters to reduce data size
4. **Reuse instances** - Use singleton pattern (`get_iv_data_provider()`)

---

## Error Handling

All methods return gracefully on errors:

```python
# Missing data returns None or empty
skew = provider.get_iv_skew("INVALID_SYMBOL")
# Returns: {"interpretation": "Data unavailable"}

options = provider.get_options_chain_with_greeks("XYZ")
# Returns: []

# Errors are logged but don't raise exceptions
```

**Check logs** for detailed error messages:
```python
import logging
logging.basicConfig(level=logging.INFO)
```

---

## Examples

**Full working examples**: `/home/user/trading/examples/iv_data_provider_usage.py`

Run examples:
```bash
cd /home/user/trading
python3 examples/iv_data_provider_usage.py
```

---

## Testing

Quick test:
```python
from src.data.iv_data_provider import get_iv_data_provider

provider = get_iv_data_provider()

# Test basic functionality
print(f"SPY IV: {provider.get_current_iv('SPY'):.4f}")
print(f"SPY IV Rank: {provider.get_iv_rank('SPY'):.2f}")
print(f"VIX: {provider.get_vix():.2f}")

# Test new methods
print(f"\nIV Skew: {provider.get_iv_skew('SPY')}")
print(f"\nTerm Structure: {provider.get_term_structure('SPY')}")
print(f"\nOptimal Covered Call: {provider.find_optimal_strikes('SPY', 'covered_call')}")
```

---

## Changelog

**2025-12-10 - Initial Release**:
- ✅ Basic IV metrics (current, rank, percentile)
- ✅ VIX integration
- ✅ Alpaca Options API integration
- ✅ Multi-source fallback (Alpaca → Calculated → VIX proxy)
- ✅ Aggressive caching (in-memory + disk)
- ✅ **NEW**: IV skew analysis (fear/greed indicator)
- ✅ **NEW**: Term structure analysis (IV across expirations)
- ✅ **NEW**: Options chain with Greeks (filtered, sorted)
- ✅ **NEW**: Optimal strike selection for 6 strategies
- ✅ **NEW**: Manual caching methods (cache_iv_data, load_cached_iv)

---

## Future Enhancements

**Planned**:
- [ ] Black-Scholes IV calculation from option prices (fallback #2)
- [ ] Historical IV database (store calculated IVs)
- [ ] IV surface visualization (3D plot of strike × expiration × IV)
- [ ] Earnings event detection (analyze IV spike patterns)
- [ ] Real-time IV alerts (notify when IV rank crosses thresholds)

---

## Support

**Questions?** Check:
1. This API documentation
2. Example scripts in `/home/user/trading/examples/`
3. Source code docstrings in `/home/user/trading/src/data/iv_data_provider.py`

**Report Issues**: Contact Claude (CTO) with:
- Symbol tested
- Error message (if any)
- Expected vs actual behavior
