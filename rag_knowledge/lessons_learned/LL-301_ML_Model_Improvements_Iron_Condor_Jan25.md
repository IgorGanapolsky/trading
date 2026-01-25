# LL-301: ML Model Improvements for Iron Condor Trading

**Date**: January 25, 2026
**Category**: Machine Learning, Strategy Optimization
**Severity**: MEDIUM (future enhancement)
**Status**: Research Complete

## Executive Summary

Research shows LSTM models outperform traditional methods for volatility prediction. Our current regime detector already implements HMM + VIX/VVIX, but could be enhanced with LSTM for better entry timing.

## Current System Capabilities

Our `src/utils/regime_detector.py` already implements:
- 4-state HMM (calm, trending, volatile, spike)
- VIX/VVIX skew analysis
- Transition prediction with leading indicators
- Composite scoring (0-1 bullish/bearish)

**Key thresholds (from code):**
```python
vix_spike_threshold: 30.0   # Pause trading
vix_calm_threshold: 15.0    # Ideal for iron condors
high_vol_threshold: 0.4     # Regime detection
```

## Research Findings

### 1. LSTM Outperforms for Short-Term Volatility

From [Springer research](https://link.springer.com/article/10.1007/s10614-025-11122-9):
- LSTM models achieve R² of 0.93 for VVIX prediction
- Best for "immense and immediate changes in implied volatility"
- Outperforms GARCH for maturities < 30 days

### 2. Hybrid LSTM-GARCH Models

From [arXiv research](https://arxiv.org/html/2407.16780v1):
- Combining LSTM with GARCH improves accuracy
- VIX input adds "forward-looking element"
- Models capture both historical patterns and market expectations

### 3. Key Features for Prediction

| Feature | Type | Importance |
|---------|------|------------|
| VIX level | Primary | High |
| VVIX/VIX ratio | Leading indicator | High |
| VIX rate of change | Momentum | Medium |
| VIX term structure | Forward-looking | Medium |
| TLT (treasury proxy) | Risk sentiment | Low |

### 4. Volatility Risk Premium (VRP)

From [Macroption](https://www.macroption.com/iron-condor-success-rate/):
- IV tends to be higher than realized HV
- This is WHY selling premium (iron condors) works
- VRP = IV - realized HV (positive = premium seller advantage)

## Proposed ML Enhancements

### Phase 1: VIX Entry Filter (Immediate)
Add VIX level check to pre-trade gate:
```python
def should_enter_iron_condor(vix: float) -> tuple[bool, str]:
    if vix < 13:
        return False, "VIX too low - premiums insufficient"
    if vix > 20:
        return False, "VIX too high - breakout risk elevated"
    return True, f"VIX at {vix} - optimal entry conditions"
```

### Phase 2: VVIX/VIX Ratio Monitor
Add leading indicator to transition prediction:
```python
# Already in regime_detector.py, but not used in trading gate
ratio = vvix / vix
if ratio > 6.0:  # Uncertainty elevated
    return False, "VVIX/VIX ratio elevated - defer entry"
```

### Phase 3: LSTM Volatility Predictor (Future)
Train LSTM to predict next-day VIX:
- Features: VIX, VVIX, VIX term structure, SPY returns
- Target: VIX_t+1
- Use for: Timing iron condor entries

## Integration with Current System

### Current Flow
```
Market Open → Regime Detector → Trade Gate → Iron Condor Execution
```

### Enhanced Flow
```
Market Open → Regime Detector → VIX Filter → VVIX Ratio Check → Trade Gate → Execution
                     ↓
              (Future: LSTM Predictor)
```

## Action Items

- [ ] Add VIX level check to trade gate (LL-300 guidelines)
- [ ] Expose VVIX/VIX ratio in trading decisions
- [ ] Log regime scores with each trade for ML training data
- [ ] Collect 90 days of paper trading data for LSTM training
- [ ] Evaluate hmmlearn model performance vs baseline

## Sources

- [Springer - ResNet-LSTM VVIX Forecasting](https://link.springer.com/article/10.1007/s10614-025-11122-9)
- [arXiv - Hybrid LSTM-GARCH S&P 500 Volatility](https://arxiv.org/html/2407.16780v1)
- [Macroption - Iron Condor Success Rate](https://www.macroption.com/iron-condor-success-rate/)
- [Option Alpha - Iron Condor Strategy](https://optionalpha.com/strategies/iron-condor)

## Tags
machine_learning, lstm, hmm, volatility_prediction, iron_condor, vix, regime_detection

---

*Researched January 25, 2026. ML enhancements are future work - current system already has solid regime detection.*
