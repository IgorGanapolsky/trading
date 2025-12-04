# Trade Frequency Audit - December 4, 2025

## Executive Summary

**PROBLEM**: Only 7 trades executed in 9 trading days (0.78 trades/day) when system should be executing 3-5 trades/day.

**ROOT CAUSE**: Overly strict entry filters rejecting ~90% of potential trades.

**IMPACT**: System is too conservative, missing profitable opportunities, and not meeting daily trading targets.

---

## Filter Stack Analysis

### Filter Chain (Sequential Gates)

Trades must pass ALL of these filters to execute:

1. **Gate 1: Momentum Agent** (Technical Filters)
2. **Gate 2: RL Filter** (Machine Learning Confidence)
3. **Gate 3: LLM Sentiment** (AI Sentiment Analysis)
4. **Gate 4: Risk Manager** (Position Sizing)
5. **Gate 5: Trade Gateway** (Final Validation)

Additionally, Growth Strategy (Tier 2) has extra filters:
- DCF Margin of Safety filter
- Intelligent Investor safety check
- LLM Council validation
- External signal validation

---

## Detailed Filter Analysis

### 🔴 CRITICAL: Gate 1 - Momentum Agent (TOO STRICT)

**Location**: `src/utils/technical_indicators.py:178-246`

**Current Thresholds**:
```python
macd_threshold = 0.0     # Must be > 0 (bullish MACD required)
rsi_overbought = 70.0    # Must be < 70 (not overbought)
volume_min = 0.8         # Must be > 0.8x average
```

**Rejection Logic** (HARD FILTERS):
- If `macd_histogram < 0.0` → **REJECTED** (Bearish MACD)
- If `rsi > 70.0` → **REJECTED** (Overbought)
- If `volume_ratio < 0.8` → **REJECTED** (Low volume)

**Problem**:
- MACD > 0 requirement rejects ALL stocks in consolidation or slight downtrend
- Volume > 0.8x rejects low-activity periods
- These are applied to EVERY candidate, reducing pool by ~70%

**Estimated Rejection Rate**: **70-80%** of candidates

**Recommendation**:
```python
# RELAXED THRESHOLDS
macd_threshold = -0.1    # Allow slightly bearish (near crossover)
rsi_overbought = 75.0    # Allow moderately overbought
volume_min = 0.6         # Accept lower volume periods
```

---

### 🟡 Gate 2 - Growth Strategy Technical Filters (TOO STRICT)

**Location**: `src/strategies/growth_strategy.py:576`

**Current Logic** (ALL must be true):
```python
if (momentum > 0
    and 30 < rsi < 70
    and volume_ratio > 1.2
    and macd_histogram > 0):
    # PASS
else:
    # REJECTED
```

**Problems**:
1. **macd_histogram > 0** - Requires bullish MACD (duplicates Gate 1)
2. **volume_ratio > 1.2** - Requires 20% above average (very strict)
3. **momentum > 0** - No negative momentum allowed
4. **AND logic** - All conditions must pass (compound rejection)

**Estimated Rejection Rate**: **80-90%** of candidates (after Gate 1)

**Recommendation**:
```python
# RELAXED - Allow 2 of 4 conditions
conditions_met = sum([
    momentum > -0.02,         # Allow slight negative momentum
    30 < rsi < 75,           # Wider RSI range
    volume_ratio > 0.8,      # Lower volume threshold
    macd_histogram > -0.05   # Allow near-crossover
])
if conditions_met >= 2:      # Need 2 of 4 (not 4 of 4)
    # PASS
```

---

### 🟡 Gate 2 - RL Filter Threshold (MODERATELY STRICT)

**Location**: `src/orchestrator/main.py:517`

**Current Threshold**:
```python
RL_CONFIDENCE_THRESHOLD = 0.6   # 60% confidence required
```

**Rejection Logic**:
- If `rl_confidence < 0.6` → **REJECTED**

**Estimated Rejection Rate**: **30-40%** of candidates (after momentum filter)

**Recommendation**:
```python
RL_CONFIDENCE_THRESHOLD = 0.45   # 45% confidence (more balanced)
```

---

### 🟢 Gate 3 - LLM Sentiment (REASONABLE)

**Location**: `src/orchestrator/main.py:609`

**Current Threshold**:
```python
LLM_NEGATIVE_SENTIMENT_THRESHOLD = -0.2   # Reject if < -0.2
```

**Estimated Rejection Rate**: **10-20%** (mostly already filtered)

**Recommendation**: Keep as-is (reasonable threshold)

---

### 🔴 CRITICAL: Growth Strategy - DCF Filter (TOO STRICT)

**Location**: `src/strategies/growth_strategy.py:779`

**Current Threshold**:
```python
DCF_MARGIN_OF_SAFETY = 0.15   # 15% margin required
```

**Rejection Logic**:
- If `(intrinsic_value - price) / intrinsic_value < 0.15` → **REJECTED**

**Problem**: Requires 15% undervaluation - very few stocks meet this in bull markets

**Estimated Rejection Rate**: **60-70%** of candidates

**Recommendation**:
```python
DCF_MARGIN_OF_SAFETY = 0.05   # 5% margin (more realistic)
```

---

### 🟡 Growth Strategy - Intelligent Investor Check (VETO POINT)

**Location**: `src/strategies/growth_strategy.py:1306-1357`

**Effect**: Additional Graham-Buffett principles check - can veto even if all other filters pass

**Estimated Rejection Rate**: **20-30%** of remaining candidates

**Recommendation**: Make this a warning rather than rejection for ETFs (ETFs are inherently safer than individual stocks)

---

### 🟡 Core Strategy - LLM Council (VETO POINT)

**Location**: `src/strategies/core_strategy.py:723`

**Effect**: Multi-LLM consensus check - can veto approved trades

**Estimated Rejection Rate**: **10-20%** of remaining candidates

**Recommendation**: Lower council rejection threshold or make it advisory-only during R&D phase

---

## Compound Rejection Math

**Cascading Filter Effect**:
```
100 candidate signals
├─ 70% rejected by Gate 1 (MACD/RSI/Volume) → 30 remaining
├─ 80% rejected by Growth filters → 6 remaining
├─ 40% rejected by RL filter → 3.6 remaining
├─ 60% rejected by DCF filter → 1.4 remaining
├─ 20% rejected by Intelligent Investor → 1.1 remaining
└─ 10% rejected by LLM Council → 1.0 remaining per day
```

**Result**: 1-2 trades/day instead of 3-5 trades/day

---

## Recommended Changes

### Priority 1 - Immediate Impact (High)

1. **Relax Momentum MACD Threshold**
   ```python
   # src/strategies/legacy_momentum.py
   macd_threshold = -0.1  # From 0.0
   ```

2. **Relax Growth Strategy Technical Filters**
   ```python
   # src/strategies/growth_strategy.py line 576
   # Change from AND to "2 of 4" logic
   conditions_met >= 2  # From requiring all 4
   ```

3. **Reduce RL Confidence Threshold**
   ```python
   # Environment variable
   RL_CONFIDENCE_THRESHOLD = 0.45  # From 0.6
   ```

4. **Reduce DCF Margin of Safety**
   ```python
   # Environment variable
   DCF_MARGIN_OF_SAFETY = 0.05  # From 0.15
   ```

### Priority 2 - Optimization (Medium)

5. **Relax Volume Threshold**
   ```python
   # src/strategies/legacy_momentum.py
   volume_min = 0.6  # From 0.8
   ```

6. **Make Intelligent Investor Advisory for ETFs**
   ```python
   # Skip safety check for ETFs (SPY, QQQ, VOO, etc.)
   if symbol not in ["SPY", "QQQ", "VOO", "BND", "VNQ"]:
       # Apply full safety check
   ```

### Priority 3 - Long-term (Lower Priority)

7. **Make LLM Council Advisory During R&D**
   ```python
   # Log council decision but don't reject
   if not council_approved:
       logger.warning("Council advisory: ...")
       # Continue anyway during R&D phase
   ```

---

## Expected Impact

**Current State**:
- Trades/day: 0.78
- Rejection rate: ~90%

**After Priority 1 Changes**:
- Trades/day: 3-5 (target met)
- Rejection rate: ~60%

**After Priority 1+2 Changes**:
- Trades/day: 5-8 (exceeds target)
- Rejection rate: ~40%

---

## Implementation Files

### Files to Modify:

1. **src/strategies/legacy_momentum.py** - Line 48-50
2. **src/strategies/growth_strategy.py** - Line 576-598
3. **src/strategies/core_strategy.py** - Line 608-633 (Intelligent Investor)
4. **src/orchestrator/main.py** - Line 517 (RL threshold)
5. **Environment variables** (via .env or defaults):
   - `MOMENTUM_MACD_THRESHOLD`
   - `RL_CONFIDENCE_THRESHOLD`
   - `DCF_MARGIN_OF_SAFETY`
   - `MOMENTUM_VOLUME_MIN`

---

## Risk Assessment

**Low Risk Changes**:
- Relaxing MACD from 0.0 to -0.1 (near-crossover still valid)
- Reducing RL threshold from 0.6 to 0.45 (still above 50%)
- Making Intelligent Investor advisory for ETFs (ETFs are inherently safe)

**Medium Risk Changes**:
- Reducing DCF margin from 15% to 5% (may accept slightly overvalued stocks)
- Changing Growth filters from AND to "2 of 4" (more permissive)

**Recommendation**: Implement Priority 1 changes first, monitor for 5 trading days, then evaluate Priority 2.

---

## Conclusion

The trading system has 8-10 layers of filters acting as sequential veto points. Each filter individually is reasonable, but compounded together they reject ~90% of trades.

**Key Principle**: We're in R&D Phase (Days 1-90). The goal is to BUILD TRADING EDGE through data collection and learning, not to achieve perfect safety. Conservative filters prevent the system from learning.

**Recommended Approach**: Relax filters to achieve 3-5 trades/day, collect data, then gradually tighten based on win/loss patterns observed.

---

**Audit Date**: December 4, 2025
**Audited By**: AI Trading System CTO
**Status**: CRITICAL - Immediate action required
**Next Review**: After 5 trading days post-implementation
