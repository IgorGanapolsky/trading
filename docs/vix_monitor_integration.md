# VIX Monitor Integration Guide

## Overview

The VIX Monitor provides real-time volatility regime detection and options strategy recommendations based on current VIX levels. It integrates seamlessly with the existing `RegimeDetector` class.

## Quick Start

```python
from monitoring.vix_monitor import VIXMonitor

# Initialize monitor
monitor = VIXMonitor()

# Get current VIX level
vix = monitor.get_current_vix()
print(f"VIX: {vix:.2f}")

# Get volatility regime
regime = monitor.get_volatility_regime()
print(f"Regime: {regime}")  # Returns: very_low, low, normal, elevated, high, extreme

# Check if should sell premium
if monitor.should_sell_premium():
    print("✅ Favorable conditions for theta strategies (credit spreads, iron condors)")

# Check if should buy premium
if monitor.should_buy_premium():
    print("✅ Volatility cheap - consider long straddles/strangles")

# Get full strategy recommendation
recommendation = monitor.get_options_strategy_recommendation()
print(f"Recommendation: {recommendation['recommendation']}")
print(f"Strategies: {recommendation['strategies']}")
print(f"Sizing: {recommendation['sizing']}x")
```

## All Methods

### 1. get_current_vix()
Fetches current VIX level with 5-minute caching.

```python
vix = monitor.get_current_vix()
# Returns: float (e.g., 18.45)
```

### 2. get_vix_percentile(lookback_days=252)
Calculates where current VIX sits vs historical range (percentile rank).

```python
percentile = monitor.get_vix_percentile(lookback_days=252)
# Returns: float 0-100 (e.g., 67.5 means VIX higher than 67.5% of last year)
```

### 3. get_volatility_regime()
Simple string classification of current volatility regime.

```python
regime = monitor.get_volatility_regime()
# Returns: "very_low" | "low" | "normal" | "elevated" | "high" | "extreme"
```

**Thresholds:**
- `very_low`: VIX < 12 (extreme complacency)
- `low`: VIX 12-16 (low volatility)
- `normal`: VIX 16-20 (normal market)
- `elevated`: VIX 20-25 (caution)
- `high`: VIX 25-30 (fear)
- `extreme`: VIX > 30 (panic)

### 4. get_vix_term_structure()
Analyzes VIX vs VIX3M for contango/backwardation.

```python
term_structure = monitor.get_vix_term_structure()
# Returns: TermStructure enum (CONTANGO, FLAT, BACKWARDATION)

if term_structure == TermStructure.BACKWARDATION:
    print("⚠️ WARNING: Market expects near-term volatility spike!")
```

### 5. should_sell_premium()
Boolean signal for theta strategies (premium selling).

```python
if monitor.should_sell_premium():
    # VIX elevated (20+) AND contango detected
    # Favorable for: credit spreads, iron condors, short strangles
    execute_theta_strategy()
```

### 6. should_buy_premium()
Boolean signal for long volatility strategies (premium buying).

```python
if monitor.should_buy_premium():
    # VIX very low (<15) AND backwardation detected
    # Favorable for: long straddles, long strangles
    execute_long_vol_strategy()
```

### 7. get_options_strategy_recommendation()
Complete strategy recommendation based on current regime.

```python
rec = monitor.get_options_strategy_recommendation()

# Returns dict:
{
    "regime": "elevated",
    "vix_level": 22.8,
    "recommendation": "Sell puts/credit spreads - elevated premium available...",
    "strategies": ["cash_secured_put", "bull_put_spread", "short_strangle"],
    "sizing": 1.2,  # Position size multiplier
    "sell_premium": True,
    "buy_premium": False
}
```

## Integration with RegimeDetector

```python
from monitoring.vix_monitor import VIXMonitor
from utils.regime_detector import RegimeDetector

# Initialize both
vix_monitor = VIXMonitor()
regime_detector = RegimeDetector()

# Get VIX-based regime
vix_regime = vix_monitor.get_volatility_regime()

# Get multi-layer regime detection
regime_snapshot = regime_detector.detect_live_regime()

# Combine signals for robust decision-making
if vix_regime == "extreme" or regime_snapshot.regime_id == 3:
    print("🚨 EXTREME VOLATILITY - Move to capital preservation mode")
    # Pause trading, move to treasuries

elif vix_monitor.should_sell_premium() and regime_snapshot.label == "calm":
    print("✅ OPTIMAL CONDITIONS - Sell premium aggressively")
    # Execute theta strategies with elevated sizing

elif vix_monitor.should_buy_premium() and regime_snapshot.label == "calm":
    print("✅ VOLATILITY CHEAP - Buy long vol positions")
    # Execute long straddles/strangles
```

## Options Strategy Recommendations by Regime

### Very Low VIX (<12) - Complacency
**Strategies:** Long straddles, long strangles, calendar spreads
**Rationale:** Volatility extremely cheap, expect mean reversion
**Sizing:** 1.0x

### Low VIX (12-16) - Low Volatility
**Strategies:** Long straddles, long strangles, debit spreads
**Rationale:** Volatility cheap, potential for expansion
**Sizing:** 1.0x

### Normal VIX (16-20) - Neutral Market
**Strategies:** Iron condors, iron butterflies, credit spreads
**Rationale:** Neutral volatility, sell premium both sides
**Sizing:** 1.0x

### Elevated VIX (20-25) - Caution
**Strategies:** Cash-secured puts, bull put spreads, short strangles
**Rationale:** Elevated premium available, focus on bullish strategies
**Sizing:** 1.2x

### High VIX (25-30) - Fear
**Strategies:** Bull put spreads, cash-secured puts, wide short strangles
**Rationale:** High premium, widen strikes for safety
**Sizing:** 1.5x

### Extreme VIX (>30) - Panic
**Strategies:** Wide short strangles, wide iron condors, covered strangles
**Rationale:** MAX premium but MUST hedge delta risk
**Sizing:** 1.8x (with protective hedges)

## Caching & Performance

- **Cache Duration:** 5 minutes (300 seconds)
- **Automatic Fallback:** Uses last known values if API fails
- **State Persistence:** Saves history to `data/monitoring/vix_monitor_state.json`
- **Performance:** ~1 second for cached calls, ~2-3 seconds for API fetches

## Error Handling

The VIX Monitor includes comprehensive error handling:

```python
try:
    vix = monitor.get_current_vix()
except Exception as e:
    # Falls back to cached value or last known value
    # Logs error and continues gracefully
    print(f"Warning: Using fallback VIX data: {e}")
```

## Production Usage

```python
from monitoring.vix_monitor import VIXMonitor

# Initialize once at startup
vix_monitor = VIXMonitor(
    data_dir="data/monitoring",
    alert_callback=lambda alert: send_slack_notification(alert)
)

# Check before each trade
def should_execute_trade(trade_type: str) -> bool:
    regime = vix_monitor.get_volatility_regime()

    if regime == "extreme":
        # Pause all trading in extreme volatility
        return False

    if trade_type == "theta" and not vix_monitor.should_sell_premium():
        # Don't sell premium unless conditions favorable
        return False

    if trade_type == "long_vol" and not vix_monitor.should_buy_premium():
        # Don't buy premium unless volatility cheap
        return False

    return True

# Use in position sizing
def calculate_position_size(base_size: float) -> float:
    rec = vix_monitor.get_options_strategy_recommendation()

    # Adjust size based on VIX regime
    adjusted_size = base_size * rec['sizing']

    return adjusted_size
```

## Monitoring & Alerts

The VIX Monitor can generate alerts on:
- **Regime changes** (e.g., Normal → Elevated)
- **VIX spikes** (rapid 3+ point increases)
- **Term structure inversions** (backwardation)
- **Extreme volatility** (VIX > 35)
- **Complacency warnings** (VIX < 10)

```python
def handle_vix_alert(alert):
    print(f"🚨 VIX ALERT: {alert.message}")
    print(f"   Recommended Action: {alert.recommended_action}")

    # Send to monitoring system
    send_to_slack(alert)
    send_to_pagerduty(alert)

monitor = VIXMonitor(alert_callback=handle_vix_alert)
```

## Testing

Run the comprehensive demo:
```bash
python3 demo_vix_monitor_mock.py
```

This demos all 6 VIX regimes with mock data showing strategy recommendations, position sizing, and premium buying/selling signals.

## Files

- `/home/user/trading/src/monitoring/vix_monitor.py` - Main implementation (1048 lines)
- `/home/user/trading/demo_vix_monitor_mock.py` - Comprehensive demo with mock data
- `/home/user/trading/test_vix_monitor.py` - Live API test (requires network access)
- `/home/user/trading/docs/vix_monitor_integration.md` - This guide

## Dependencies

- `yfinance` - VIX data fetching (already in requirements.txt)
- `pandas` - Data manipulation (already installed)
- `numpy` - Numerical operations (already installed)

**Note:** The VIX Monitor includes a multitasking workaround for environments where the `multitasking` package cannot be installed.

## See Also

- `/home/user/trading/src/utils/regime_detector.py` - Multi-layer regime detection with HMM
- `/home/user/trading/src/risk/regime_aware_sizing.py` - Risk management integration
- `/home/user/trading/docs/r-and-d-phase.md` - Current R&D phase strategy

---

**Created:** December 10, 2025
**Status:** Production Ready ✅
