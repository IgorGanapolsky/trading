# VIX Monitor Usage Guide

## Overview

The VIX Monitor system provides comprehensive volatility analysis and regime detection for options trading. It integrates seamlessly with the existing options trading infrastructure.

## Components

### 1. VIXMonitor

Core monitoring class that fetches VIX data and calculates metrics.

```python
from src.options.vix_monitor import VIXMonitor

# Initialize monitor
monitor = VIXMonitor(use_alpaca=True)  # Use Alpaca if available, fallback to yfinance

# Get current VIX
current_vix = monitor.get_current_vix()  # e.g., 18.5

# Get VIX percentile (historical context)
percentile = monitor.get_vix_percentile(lookback_days=252)  # 1 year lookback

# Get volatility regime
regime = monitor.get_volatility_regime()  # VolatilityRegime.NORMAL

# Get term structure
term_structure = monitor.get_vix_term_structure()
# {
#   'vx1': 18.0,  # Front month
#   'vx2': 19.0,  # Second month
#   'vx3': 20.0,  # Third month
#   'overall_slope': 2.0  # Positive = contango
# }

# Check term structure state
is_contango = monitor.is_contango()  # True/False
is_backwardation = monitor.is_backwardation()  # True/False

# Get VVIX (volatility of VIX)
vvix = monitor.get_vvix()  # e.g., 95.0

# Detect VIX spikes
spike_info = monitor.detect_vix_spike()
# {
#   'is_spike': False,
#   'z_score': 1.2,
#   'severity': 'mild'
# }

# Calculate mean reversion probability
reversion_prob = monitor.calculate_mean_reversion_probability()  # 0.0 to 1.0

# Get comprehensive statistics
stats = monitor.calculate_vix_statistics(lookback_days=252)
# {
#   'current': 18.5,
#   'mean': 16.2,
#   'std': 5.3,
#   'min': 9.1,
#   'max': 82.7,
#   'percentile': 65.2,
#   'z_score': 0.43
# }
```

### 2. VIXSignals

Trading signal generator based on VIX analysis.

```python
from src.options.vix_monitor import VIXSignals

# Initialize signals (uses VIXMonitor internally)
signals = VIXSignals()

# Check if should sell premium
sell_signal = signals.should_sell_premium()
# {
#   'should_sell_premium': True,
#   'confidence': 'HIGH',
#   'current_vix': 28.0,
#   'regime': 'high',
#   'percentile': 85.0,
#   'reversion_probability': 0.85,
#   'rationale': 'VIX at 28.00 (high, 85th percentile) with 85% mean reversion probability...',
#   'recommended_strategies': ['Iron Condors', 'Credit Spreads', 'Short Strangles']
# }

# Check if should buy premium
buy_signal = signals.should_buy_premium()
# {
#   'should_buy_premium': False,
#   'confidence': 'LOW',
#   ...
# }

# Get position size multiplier
position_size = signals.get_position_size_multiplier()
# {
#   'multiplier': 0.5,  # 50% of normal size in high VIX
#   'regime': 'high',
#   'percentile': 85.0,
#   'guidance': 'CONSERVATIVE: Reduce position sizes (50-90% of normal)'
# }

# Get comprehensive strategy recommendation
recommendation = signals.get_strategy_recommendation()
# {
#   'primary_action': 'SELL_PREMIUM',
#   'regime': 'high',
#   'current_vix': 28.0,
#   'position_size_multiplier': 0.5,
#   'recommended_strategies': [
#     {'strategy': 'Iron Condor', 'action': 'SELL', 'priority': 'HIGH'},
#     {'strategy': 'Credit Spreads', 'action': 'SELL', 'priority': 'HIGH'}
#   ],
#   'risk_level': 'HIGH',
#   'entry_rules': [...],
#   'exit_rules': [...]
# }
```

## Volatility Regimes

### EXTREME_LOW (VIX < 12)
- **Strategy**: Sell premium aggressively
- **Position Size**: 1.5-2.0x normal
- **Recommended**: Iron Condors (wide), Covered Calls, Cash-Secured Puts
- **Risk**: LOW

### LOW (VIX 12-15)
- **Strategy**: Sell premium with larger positions
- **Position Size**: 1.25x normal
- **Recommended**: Iron Condors, Bull Put Spreads, Bear Call Spreads
- **Risk**: LOW-MEDIUM

### NORMAL (VIX 15-20)
- **Strategy**: Standard strategies
- **Position Size**: 1.0x normal
- **Recommended**: Balanced approach, all strategies viable
- **Risk**: MEDIUM

### ELEVATED (VIX 20-25)
- **Strategy**: Reduce position sizes
- **Position Size**: 0.75x normal
- **Recommended**: Credit Spreads (defined risk), cautious premium selling
- **Risk**: MEDIUM-HIGH

### HIGH (VIX 25-35)
- **Strategy**: Buy volatility, hedge positions
- **Position Size**: 0.5x normal
- **Recommended**: Debit Spreads, Long Straddles, protective strategies
- **Risk**: HIGH

### EXTREME (VIX > 35)
- **Strategy**: Crisis mode, capital preservation
- **Position Size**: 0.25x normal
- **Recommended**: Cash, protective puts, minimal exposure
- **Risk**: EXTREME

## Term Structure States

### Contango (VX2 > VX1)
- **Meaning**: Normal market, volatility expected to decay
- **Implication**: Favorable for premium selling
- **Typical**: VIX in normal to low range
- **Strategy**: Sell time premium (theta decay works in your favor)

### Backwardation (VX1 > VX2)
- **Meaning**: Fear mode, expect volatility spike
- **Implication**: Caution with premium selling, consider buying premium
- **Typical**: Market stress, VIX spiking
- **Strategy**: Buy volatility, reduce exposure, hedge

### Flat
- **Meaning**: Neutral, no clear direction
- **Implication**: Wait for clearer signals
- **Strategy**: Reduce position sizes, await regime shift

## Integration with Options Executor

```python
from src.options.vix_monitor import VIXMonitor, VIXSignals
from src.trading.options_executor import OptionsExecutor

# Initialize components
monitor = VIXMonitor()
signals = VIXSignals(monitor)
executor = OptionsExecutor(paper=True)

# Get current regime
regime = monitor.get_volatility_regime()
print(f"Current Regime: {regime.value}")

# Get strategy recommendation
recommendation = signals.get_strategy_recommendation()
print(f"Primary Action: {recommendation['primary_action']}")

# Adjust position sizing based on VIX
position_multiplier = signals.get_position_size_multiplier()

# Example: Execute trade with VIX-adjusted sizing
if recommendation['primary_action'] == 'SELL_PREMIUM':
    if regime.value in ['high', 'elevated']:
        # Sell iron condor with reduced size
        result = executor.execute_iron_condor(
            ticker='SPY',
            width=5.0,
            target_delta=0.16,  # Further OTM in high VIX
            dte=30  # Shorter DTE to avoid gamma risk
        )
        print(f"Iron Condor executed: {result}")

elif recommendation['primary_action'] == 'BUY_PREMIUM':
    if regime.value in ['extreme_low', 'low']:
        # Buy debit spreads when volatility cheap
        result = executor.execute_credit_spread(
            ticker='SPY',
            spread_type='bull_put',  # But structured as debit for long vol
            width=5.0,
            dte=45
        )
        print(f"Debit spread executed: {result}")
```

## State Export for System Integration

Export VIX state to `system_state.json`:

```python
from src.options.vix_monitor import VIXMonitor

monitor = VIXMonitor()
vix_state = monitor.export_state()

# vix_state contains:
# {
#   'current_vix': 18.5,
#   'volatility_regime': 'normal',
#   'vix_percentile': 55.0,
#   'term_structure': {
#     'state': 'contango',
#     'vx1': 18.0,
#     'vx2': 19.0,
#     'vx3': 20.0,
#     'slope': 2.0
#   },
#   'statistics': {...},
#   'vvix': 95.0,
#   'spike_detected': False,
#   'mean_reversion_probability': 0.45,
#   'last_updated': '2025-12-10T10:30:00'
# }

# Add to system_state.json
import json
with open('data/system_state.json', 'r') as f:
    system_state = json.load(f)

system_state['vix_monitor'] = vix_state

with open('data/system_state.json', 'w') as f:
    json.dump(system_state, f, indent=2)
```

## Historical VIX Data

VIX history is automatically stored in `data/vix_history.json`:

```json
{
  "daily_values": [
    {
      "date": "2025-12-10",
      "vix": 18.5,
      "timestamp": "2025-12-10T10:00:00"
    },
    ...
  ],
  "last_updated": "2025-12-10T10:00:00",
  "metadata": {
    "created": "2025-12-10T09:00:00",
    "source": "vix_monitor"
  }
}
```

Maximum 504 days (2 years) of history stored.

## Example: Daily Trading Workflow

```python
from src.options.vix_monitor import VIXMonitor, VIXSignals
from src.trading.options_executor import OptionsExecutor

def daily_vix_check():
    """Run VIX analysis before trading"""

    # 1. Initialize
    monitor = VIXMonitor()
    signals = VIXSignals(monitor)

    # 2. Get current state
    vix = monitor.get_current_vix()
    regime = monitor.get_volatility_regime()

    # 3. Check for spikes
    spike = monitor.detect_vix_spike()
    if spike['is_spike']:
        print(f"⚠️ VIX SPIKE DETECTED! Severity: {spike['severity']}")
        print("Recommendation: REDUCE POSITIONS or WAIT")
        return False  # Don't trade during spikes

    # 4. Get strategy recommendation
    recommendation = signals.get_strategy_recommendation()

    print(f"VIX: {vix:.2f} ({regime.value.upper()})")
    print(f"Primary Action: {recommendation['primary_action']}")
    print(f"Position Size: {recommendation['position_size_multiplier']:.2f}x")

    # 5. Execute trades based on recommendation
    if recommendation['primary_action'] == 'SELL_PREMIUM':
        print("✅ Conditions favor PREMIUM SELLING")
        for strat in recommendation['recommended_strategies']:
            print(f"  - {strat['strategy']} ({strat['priority']} priority)")
        return True

    elif recommendation['primary_action'] == 'BUY_PREMIUM':
        print("✅ Conditions favor PREMIUM BUYING")
        for strat in recommendation['recommended_strategies']:
            print(f"  - {strat['strategy']} ({strat['priority']} priority)")
        return True

    else:
        print("⏸️ WAIT - No clear edge")
        return False

# Run daily check
if daily_vix_check():
    print("\n✅ Proceeding with options trading")
else:
    print("\n⏸️ Waiting for better conditions")
```

## Testing

Run tests:

```bash
# Run all VIX monitor tests
python3 -m pytest tests/test_vix_monitor.py -v

# Run specific test
python3 -m pytest tests/test_vix_monitor.py::TestVIXMonitor::test_get_current_vix -v

# Run with coverage
python3 -m pytest tests/test_vix_monitor.py --cov=src.options.vix_monitor --cov-report=html
```

## Troubleshooting

### Issue: "No module named 'yfinance'"

**Solution**: Install yfinance:
```bash
pip install yfinance
```

### Issue: "Unable to fetch VIX data"

**Possible causes**:
1. Network connectivity issues
2. Yahoo Finance API temporarily down
3. Alpaca API credentials missing/invalid

**Solutions**:
1. Check internet connection
2. Wait and retry (Yahoo Finance occasionally rate limits)
3. Verify `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` environment variables

### Issue: VIX percentile returns 50.0 (default)

**Cause**: Insufficient historical data

**Solution**: This is a fallback when historical data unavailable. The monitor will automatically fetch data on next run.

## Performance Considerations

- **VIX data fetch**: ~1-2 seconds (cached in `vix_history.json`)
- **Percentile calculation**: ~0.5 seconds (252 days of data)
- **Term structure**: ~2-3 seconds (fetches VIX + VXV)
- **Full state export**: ~5 seconds (all metrics)

**Recommendation**: Fetch VIX data once per day (during market open), cache results.

## Next Steps

1. **Integration with main trading loop**: Add VIX check before executing options trades
2. **Alerts**: Create alerts for VIX regime changes (e.g., LOW → ELEVATED)
3. **Backtesting**: Test VIX-based position sizing on historical data
4. **Dashboard**: Add VIX metrics to Streamlit dashboard
5. **Automation**: Auto-adjust strategy selection based on VIX regime

## References

- VIX Methodology: https://www.cboe.com/tradable_products/vix/
- VIX Futures: https://www.cmegroup.com/markets/equities/volatility/volatility.html
- McMillan on Volatility: "Options as a Strategic Investment"
- TastyTrade Research: https://www.tastytrade.com/research
