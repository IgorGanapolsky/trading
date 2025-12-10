# VIX Monitor - Quick Start Guide

**30-Second Setup | Immediate Use**

---

## Fastest Path to VIX Monitoring

### 1. Basic VIX Check (2 lines)

```python
from src.options.vix_monitor import get_vix_monitor

monitor = get_vix_monitor()
current_vix = monitor.get_current_vix()  # Done!
print(f"VIX: {current_vix:.2f}")
```

### 2. Get Trading Signal (3 lines)

```python
from src.options.vix_monitor import get_vix_signals

signals = get_vix_signals()
recommendation = signals.get_strategy_recommendation()
print(f"Action: {recommendation['primary_action']}")
```

### 3. Complete Daily Check (5 lines)

```python
from src.options.vix_monitor import VIXMonitor, VIXSignals

monitor = VIXMonitor()
signals = VIXSignals(monitor)

# Get everything
vix = monitor.get_current_vix()
regime = monitor.get_volatility_regime()
recommendation = signals.get_strategy_recommendation()

print(f"VIX: {vix:.2f} | Regime: {regime.value} | Action: {recommendation['primary_action']}")
```

---

## Most Common Use Cases

### Should I Sell Premium Today?

```python
from src.options.vix_monitor import VIXSignals

signals = VIXSignals()
sell_signal = signals.should_sell_premium()

if sell_signal['should_sell_premium']:
    print(f"✅ YES - {sell_signal['confidence']} confidence")
    print(f"Strategies: {', '.join(sell_signal['recommended_strategies'])}")
else:
    print("❌ NO - Wait for better conditions")
```

### How Big Should My Position Be?

```python
from src.options.vix_monitor import VIXSignals

signals = VIXSignals()
position_size = signals.get_position_size_multiplier()

print(f"Position Size: {position_size['multiplier']:.2f}x normal")
print(f"Guidance: {position_size['guidance']}")
```

### Is VIX Spiking? (Danger Check)

```python
from src.options.vix_monitor import VIXMonitor

monitor = VIXMonitor()
spike = monitor.detect_vix_spike()

if spike['is_spike']:
    print(f"⚠️ SPIKE DETECTED! Severity: {spike['severity']}")
    print("🛑 Consider halting new positions")
else:
    print("✅ VIX stable - safe to trade")
```

### What's the VIX Regime?

```python
from src.options.vix_monitor import VIXMonitor

monitor = VIXMonitor()
regime = monitor.get_volatility_regime()

regime_guidance = {
    'extreme_low': '🚀 Aggressive premium selling',
    'low': '📈 Premium selling with larger size',
    'normal': '⚖️ Standard strategies',
    'elevated': '⚠️ Reduce position sizes',
    'high': '🛡️ Buy volatility, hedge',
    'extreme': '🚨 Crisis mode - preserve capital'
}

print(f"Regime: {regime.value.upper()}")
print(f"Guidance: {regime_guidance[regime.value]}")
```

### Complete Pre-Trade Checklist

```python
from src.options.vix_monitor import VIXMonitor, VIXSignals

def pre_trade_vix_check() -> bool:
    """Run before opening any options position"""
    monitor = VIXMonitor()
    signals = VIXSignals(monitor)

    # 1. Check for spikes
    spike = monitor.detect_vix_spike()
    if spike['is_spike'] and spike['severity'] in ['severe', 'extreme']:
        print("🛑 HALT: Severe VIX spike detected")
        return False

    # 2. Get regime
    regime = monitor.get_volatility_regime()
    print(f"VIX Regime: {regime.value.upper()}")

    # 3. Get recommendation
    rec = signals.get_strategy_recommendation()
    print(f"Primary Action: {rec['primary_action']}")
    print(f"Position Size: {rec['position_size_multiplier']:.2f}x")

    if rec['primary_action'] == 'WAIT':
        print("⏸️ Waiting for better VIX conditions")
        return False

    # 4. Show strategies
    print("\nRecommended Strategies:")
    for strat in rec['recommended_strategies']:
        print(f"  - [{strat['priority']}] {strat['strategy']}")

    return True

# Use it
if pre_trade_vix_check():
    print("\n✅ VIX check passed - proceed with trading")
else:
    print("\n❌ VIX check failed - wait")
```

---

## Integration with Options Executor

### Execute Trade with VIX-Adjusted Parameters

```python
from src.options.vix_monitor import VIXMonitor, VIXSignals
from src.trading.options_executor import OptionsExecutor

# Initialize
monitor = VIXMonitor()
signals = VIXSignals(monitor)
executor = OptionsExecutor(paper=True)

# Get VIX-based parameters
regime = monitor.get_volatility_regime()
recommendation = signals.get_strategy_recommendation()

# Adjust strategy based on regime
if recommendation['primary_action'] == 'SELL_PREMIUM':
    # High VIX: Further OTM, shorter DTE
    if regime.value in ['high', 'extreme']:
        result = executor.execute_iron_condor(
            ticker='SPY',
            width=5.0,
            target_delta=0.16,  # ~84% P.OTM
            dte=30
        )
    # Normal VIX: Standard parameters
    else:
        result = executor.execute_iron_condor(
            ticker='SPY',
            width=5.0,
            target_delta=0.20,
            dte=45
        )
```

---

## Copy-Paste Templates

### Template 1: Morning VIX Check

```python
# Morning VIX Check Template
from src.options.vix_monitor import VIXMonitor, VIXSignals

monitor = VIXMonitor()
signals = VIXSignals(monitor)

print("=== MORNING VIX CHECK ===")
vix = monitor.get_current_vix()
regime = monitor.get_volatility_regime()
rec = signals.get_strategy_recommendation()

print(f"VIX: {vix:.2f} ({regime.value})")
print(f"Action: {rec['primary_action']}")
print(f"Position Size: {rec['position_size_multiplier']:.2f}x")

# Spike check
spike = monitor.detect_vix_spike()
if spike['is_spike']:
    print(f"⚠️ SPIKE: {spike['severity']}")
```

### Template 2: Export to System State

```python
# Export VIX State Template
import json
from src.options.vix_monitor import VIXMonitor

monitor = VIXMonitor()
vix_state = monitor.export_state()

# Load system state
with open('data/system_state.json', 'r') as f:
    system_state = json.load(f)

# Update with VIX
system_state['vix_monitor'] = vix_state

# Save
with open('data/system_state.json', 'w') as f:
    json.dump(system_state, f, indent=2)

print("✅ VIX state exported")
```

### Template 3: VIX-Based Position Sizing

```python
# VIX-Based Position Sizing Template
from src.options.vix_monitor import VIXSignals

signals = VIXSignals()
position_size = signals.get_position_size_multiplier()

# Standard position size
base_contracts = 5

# Adjust based on VIX
adjusted_contracts = int(base_contracts * position_size['multiplier'])

print(f"Base: {base_contracts} contracts")
print(f"VIX Multiplier: {position_size['multiplier']:.2f}x")
print(f"Adjusted: {adjusted_contracts} contracts")
print(f"Guidance: {position_size['guidance']}")
```

---

## Key Regime Thresholds (Memorize These)

| VIX Level | Regime | Action |
|-----------|--------|--------|
| < 12 | EXTREME_LOW | Sell premium aggressively (2x size) |
| 12-15 | LOW | Sell premium (1.25x size) |
| 15-20 | NORMAL | Standard strategies (1x size) |
| 20-25 | ELEVATED | Reduce size (0.75x) |
| 25-35 | HIGH | Buy volatility (0.5x size) |
| > 35 | EXTREME | Preserve capital (0.25x size) |

---

## Troubleshooting

### "Module not found"
```bash
# Ensure you're in the trading directory
cd /home/user/trading

# Test import
python3 -c "from src.options.vix_monitor import VIXMonitor; print('✅ Works')"
```

### "Unable to fetch VIX"
- Check internet connection
- Wait 30 seconds and retry (rate limiting)
- Use fallback: VIX data updates once daily, not critical for real-time

### Test Without Live Data
```python
from src.options.vix_monitor import VIXMonitor

monitor = VIXMonitor(use_alpaca=False)  # Use yfinance only
regime = monitor.get_volatility_regime(vix_value=18.5)  # Manual VIX
print(regime.value)  # Works without fetching
```

---

## Next Steps

1. **Test in Python REPL**
   ```bash
   python3
   >>> from src.options.vix_monitor import get_vix_monitor
   >>> monitor = get_vix_monitor()
   >>> vix = monitor.get_current_vix()
   >>> print(f"VIX: {vix}")
   ```

2. **Add to Daily Workflow**
   - Run morning VIX check before trading
   - Export to system_state.json daily
   - Use for position sizing

3. **Integrate with Options Executor**
   - See `examples/vix_monitor_integration.py`
   - VIX-based strategy selection
   - Dynamic position sizing

4. **Set Up Alerts**
   - Alert when VIX regime changes
   - Alert on VIX spikes
   - Alert on backwardation

---

## One-Liner Reference

```python
# Get VIX
from src.options.vix_monitor import get_vix_monitor; print(f"VIX: {get_vix_monitor().get_current_vix():.2f}")

# Get Signal
from src.options.vix_monitor import get_vix_signals; print(get_vix_signals().get_strategy_recommendation()['primary_action'])

# Check Spike
from src.options.vix_monitor import VIXMonitor; print("⚠️ SPIKE" if VIXMonitor().detect_vix_spike()['is_spike'] else "✅ OK")
```

---

**That's it! You're ready to use VIX monitoring in your options trading.** 🚀

For detailed documentation, see:
- `docs/vix_monitor_usage.md` - Complete usage guide
- `docs/VIX_MONITOR_SYSTEM.md` - System overview
- `examples/vix_monitor_integration.py` - Full integration example
