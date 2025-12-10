# Options IV Data Integration

Real-time Implied Volatility (IV) analysis and integration with Alpaca Options API.

## Overview

The `iv_data_integration.py` module provides comprehensive IV analysis for options trading:

- **IVDataFetcher**: Fetch and analyze IV data from Alpaca
- **VolatilitySurface**: Build 3D volatility surfaces and detect arbitrage
- **IVAlerts**: Generate trading alerts based on IV conditions
- **BlackScholesIV**: Calculate IV from option prices

## Quick Start

### Basic IV Analysis

```python
from src.options.iv_data_integration import IVDataFetcher, IVAlerts

# Initialize fetcher (paper trading by default)
fetcher = IVDataFetcher(paper=True, cache_ttl_minutes=5)

# Get comprehensive IV metrics
metrics = fetcher.get_iv_metrics("SPY")

print(f"Current IV: {metrics.current_iv:.2%}")
print(f"IV Percentile: {metrics.iv_percentile:.1f}%")
print(f"IV Regime: {metrics.iv_regime.value}")
print(f"Recommendation: {metrics.recommendation}")

# Check for trading alerts
alerts_system = IVAlerts(fetcher)
alerts = alerts_system.check_all_alerts("SPY")

if alerts:
    print(alerts_system.format_alert_report(alerts))
```

### Volatility Surface Analysis

```python
from src.options.iv_data_integration import VolatilitySurface

surface_builder = VolatilitySurface(fetcher)

# Build 3D surface from option chain
surface = surface_builder.build_surface("SPY")

# Interpolate IV for any strike/DTE
iv_estimate = surface_builder.interpolate_iv(
    surface,
    target_strike=600.0,
    target_dte=30
)

# Detect arbitrage opportunities
opportunities = surface_builder.detect_arbitrage_opportunities(surface)
for opp in opportunities:
    print(f"Arbitrage: {opp['type']} at strike ${opp['strike']}")
```

### Daily IV Snapshot Collection

```python
# Save daily IV snapshot for percentile calculation
# Run this at market close each day

fetcher = IVDataFetcher(paper=True)
metrics = fetcher.get_iv_metrics("SPY")
fetcher.save_iv_snapshot("SPY", metrics.atm_iv, metrics.current_price)
```

## Features

### 1. IVDataFetcher

**Methods:**
- `get_option_chain(symbol)` - Fetch full option chain from Alpaca
- `get_atm_iv(symbol, dte_target=30)` - Get at-the-money IV
- `calculate_iv_percentile(symbol, lookback_days=252)` - IV percentile rank
- `get_iv_skew(symbol, dte_target=30)` - Put/call IV differential
- `get_term_structure(symbol)` - IV across expirations
- `detect_iv_regime(symbol)` - Classify IV level (low/normal/high/extreme)
- `get_iv_metrics(symbol)` - **Main entry point** - comprehensive analysis

**IV Regimes:**
- `EXTREME_LOW` (< 10th percentile) - Buy vol aggressively
- `LOW` (10-30th percentile) - Favor buying vol
- `NORMAL` (30-70th percentile) - Neutral
- `HIGH` (70-90th percentile) - Favor selling vol
- `EXTREME_HIGH` (> 90th percentile) - Sell vol aggressively

### 2. VolatilitySurface

**Methods:**
- `build_surface(symbol)` - Construct 3D vol surface
- `interpolate_iv(surface, strike, dte)` - Estimate IV for any point
- `detect_arbitrage_opportunities(surface)` - Find mispricing

**Arbitrage Checks:**
- Calendar spreads (front > back month at same strike)
- Vertical spreads (call spreads with negative value)
- Butterfly mispricing

### 3. IVAlerts

**Alert Types:**
- `SELL_VOL` - IV percentile > 80% (sell premium opportunity)
- `BUY_VOL` - IV percentile < 20% (buy premium opportunity)
- `IV_SKEW` - Extreme put/call IV difference (> 5%)
- `TERM_INVERSION` - Front month IV > back month (fear indicator)

**Methods:**
- `check_all_alerts(symbol)` - Check all conditions
- `format_alert_report(alerts)` - Human-readable report

### 4. BlackScholesIV

**Methods:**
- `calculate_call_price(S, K, T, r, sigma)` - Theoretical call price
- `calculate_put_price(S, K, T, r, sigma)` - Theoretical put price
- `calculate_iv(option_price, S, K, T, r, option_type)` - Implied vol from price

**Use Cases:**
- Validate Alpaca IV data
- Calculate IV for custom option prices
- Educational purposes

## CLI Usage

```bash
# Analyze SPY
python3 src/options/iv_data_integration.py SPY

# Analyze with snapshot saving
python3 src/options/iv_data_integration.py AAPL --save-snapshot

# Disable caching for fresh data
python3 src/options/iv_data_integration.py QQQ --no-cache
```

## Integration with Existing Code

This module integrates with:
- `src/utils/iv_analyzer.py` - Uses yfinance (historical analysis)
- `src/signals/options_iv_signal_generator.py` - Strategy recommendations
- `src/core/options_client.py` - Alpaca API client

**Key Differences:**
- `iv_analyzer.py` uses **yfinance** (historical, slower)
- `iv_data_integration.py` uses **Alpaca** (real-time, faster, live trading)

## Data Storage

**IV History Cache:**
- Location: `data/iv_cache/{SYMBOL}_iv_history.json`
- Format: `[{"date": "2025-12-10", "iv": 0.20, "price": 600.0}, ...]`
- Purpose: Percentile calculations (requires 252 days)

**Build History:**
```bash
# Collect daily snapshots (run at market close)
python3 -c "
from src.options.iv_data_integration import IVDataFetcher
fetcher = IVDataFetcher()
for symbol in ['SPY', 'QQQ', 'IWM']:
    metrics = fetcher.get_iv_metrics(symbol)
    fetcher.save_iv_snapshot(symbol, metrics.atm_iv, metrics.current_price)
    print(f'{symbol}: {metrics.atm_iv:.2%}')
"
```

## Performance

**Caching:**
- Option chains cached for 5 minutes (configurable)
- IV history cached on disk (6-hour TTL)
- Metrics cached in memory (TTL-based)

**Rate Limiting:**
- Alpaca API: 200 requests/minute
- Use caching to stay within limits
- Batch requests when possible

## Error Handling

All methods include graceful error handling:
- Missing data returns `None` or neutral values
- API failures logged but don't crash
- Invalid inputs validated with clear error messages

## Testing

```bash
# Run all tests
pytest tests/test_iv_integration.py -v

# Run specific test class
pytest tests/test_iv_integration.py::TestIVDataFetcher -v

# Run with coverage
pytest tests/test_iv_integration.py --cov=src.options.iv_data_integration
```

## Dependencies

Required packages:
- `alpaca-py` - Alpaca API client
- `numpy` - Numerical computations
- `scipy` - Interpolation and statistics
- `python-dateutil` - Date parsing

Install:
```bash
pip install alpaca-py numpy scipy python-dateutil
```

## Examples

### Example 1: Daily IV Monitoring

```python
from src.options.iv_data_integration import IVDataFetcher, IVAlerts

watchlist = ["SPY", "QQQ", "IWM", "DIA"]

fetcher = IVDataFetcher(paper=True)
alerts_system = IVAlerts(fetcher)

for symbol in watchlist:
    metrics = fetcher.get_iv_metrics(symbol)
    alerts = alerts_system.check_all_alerts(symbol)

    print(f"\n{symbol}:")
    print(f"  IV: {metrics.current_iv:.2%} (Percentile: {metrics.iv_percentile:.0f}%)")
    print(f"  Regime: {metrics.iv_regime.value.upper()}")
    print(f"  Recommendation: {metrics.recommendation}")

    if alerts:
        print(f"  🚨 {len(alerts)} alerts triggered!")
```

### Example 2: IV Skew Analysis

```python
from src.options.iv_data_integration import IVDataFetcher

fetcher = IVDataFetcher()

symbols = ["AAPL", "TSLA", "NVDA"]
for symbol in symbols:
    skew = fetcher.get_iv_skew(symbol, dte_target=30)

    if skew < -0.05:
        print(f"{symbol}: Bearish skew ({skew:.2%}) - Puts expensive")
    elif skew > 0.05:
        print(f"{symbol}: Bullish skew ({skew:.2%}) - Calls expensive")
    else:
        print(f"{symbol}: Neutral skew ({skew:.2%})")
```

### Example 3: Term Structure Analysis

```python
from src.options.iv_data_integration import IVDataFetcher

fetcher = IVDataFetcher()
term_structure = fetcher.get_term_structure("SPY")

print("SPY Term Structure:")
for dte, iv in sorted(term_structure.items()):
    print(f"  {dte:3d} days: {iv:.2%}")

slope = fetcher.calculate_term_structure_slope(term_structure)
if slope > 0:
    print(f"\nNormal term structure (slope: {slope:.6f})")
else:
    print(f"\n⚠️ INVERTED term structure (slope: {slope:.6f}) - FEAR!")
```

## Architecture

```
iv_data_integration.py
├── IVDataFetcher (main class)
│   ├── get_option_chain()
│   ├── calculate_iv_percentile()
│   ├── get_iv_skew()
│   ├── get_term_structure()
│   ├── get_atm_iv()
│   ├── detect_iv_regime()
│   └── get_iv_metrics() ⭐ (main entry point)
│
├── VolatilitySurface
│   ├── build_surface()
│   ├── interpolate_iv()
│   └── detect_arbitrage_opportunities()
│
├── IVAlerts
│   ├── check_all_alerts()
│   └── format_alert_report()
│
└── BlackScholesIV
    ├── calculate_call_price()
    ├── calculate_put_price()
    └── calculate_iv()
```

## Roadmap

Future enhancements:
- [ ] Real-time IV streaming (WebSocket integration)
- [ ] Multi-symbol correlation analysis
- [ ] ML-based IV prediction
- [ ] Historical IV backfilling automation
- [ ] Alert notifications (Slack, email)
- [ ] Streamlit dashboard integration

## License

Part of the AI Trading System. See project root for license.

---

**Author:** Claude (CTO)
**Created:** 2025-12-10
**Version:** 1.0.0
