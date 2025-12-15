# Lesson Learned: Pyramid Buying During Fear Destroyed $96 (Dec 15, 2025)

**ID**: ll_020
**Date**: December 15, 2025
**Severity**: CRITICAL
**Category**: Strategy, Risk Management, Behavioral Finance, Data Integrity
**Impact**: Portfolio lost $96 in 5 days, 0% win rate on fear-based trades

## Executive Summary

The "buy the dip" strategy during "Extreme Fear" conditions was catching falling knives with 0% win rate. The system was programmed to BUY MORE (1.5-2x) when the market was falling, which is the opposite of what works for retail traders. Additionally, misleading backtest metrics ("62.2% win rate, 2.18 Sharpe") were hardcoded in hooks despite never existing in any actual data.

## The Problem

### What Happened (Dec 13-15, 2025)

| Date | Fear/Greed Index | Action | Result |
|------|------------------|--------|--------|
| Dec 13 | 21 (Extreme Fear) | BUY 1.5x ETHUSD | Loss |
| Dec 13 | 21 (Extreme Fear) | BUY 1.5x BTCUSD | Loss |
| Dec 14 | 16 (Extreme Fear) | BUY 1.5x ETHUSD | Loss |
| Dec 14 | 16 (Extreme Fear) | BUY 1.5x BTCUSD | Loss |

**Portfolio Impact**: +$17.49 → -$96.19 (lost $113.68 in 5 days)

### Root Causes

1. **Contrarian Timing Doesn't Work for Retail**
   - Fear Greed Index at 21 was NOT the bottom
   - "Extreme Fear" can persist for weeks in downtrends
   - Research shows trend following beats contrarian for retail (97% of day traders lose)

2. **Size Multiplier Amplified Losses**
   ```python
   # BEFORE (WRONG):
   if value <= EXTREME_FEAR_THRESHOLD:
       size_multiplier = 1.5  # Buy 50% MORE during fear
   ```

3. **Buy The Dip Logic Caught Falling Knives**
   ```python
   # BEFORE (WRONG):
   if btc_change <= -2.0:
       multiplier = min(2.0, 1.0 + abs(btc_change) / 10)  # Up to 2x during dips
   ```

4. **Misleading Metrics in Hooks**
   - Hooks showed: "62.2% win rate, 2.18 Sharpe"
   - Reality: 0/13 scenarios pass, Sharpe -7 to -2086 (ALL NEGATIVE)
   - The 2.18 Sharpe NEVER EXISTED in any backtest data

### Evidence from Live Trades

| Strategy | P/L | Win Rate | Status |
|----------|-----|----------|--------|
| Options (short) | +$327.82 | 100% | WORKED |
| Crypto (long) | -$0.43 | 0% | FAILED |
| Equities (long) | -$4.15 | ~40% | MARGINAL |

**Options selling was the actual edge. Crypto buying had zero edge.**

## The Fix

### 1. Disabled Fear Size Multiplier

**File**: `src/utils/fear_greed_index.py`

```python
# AFTER (CORRECT):
if value <= self.EXTREME_FEAR_THRESHOLD:
    action = "HOLD"  # Changed from BUY
    size_multiplier = 1.0  # Changed from 1.5
    confidence = 0.3  # Low confidence - fear can persist
    reasoning = f"Extreme Fear ({value}) - WAITING for trend confirmation."
```

### 2. Reversed Buy The Dip Logic

**File**: `src/strategies/crypto_strategy.py`

```python
# AFTER (CORRECT):
if btc_change <= -2.0:
    multiplier = 0.5  # REDUCE position during downtrend, don't increase
    logger.info(f"⚠️  BTC DIP: REDUCING position - DON'T CATCH FALLING KNIVES")
```

### 3. Honest Metrics in Hooks

**Files**: `.claude/hooks/inject_trading_context.sh`, `load_trading_state.sh`

```bash
# AFTER (CORRECT):
Win Rate: $WIN_RATE% (live) | Backtest: 0/13 scenarios pass (Sharpe all negative)
Backtest Reality: 0/13 pass | Sharpe: -7 to -2086 | NO EDGE YET
```

## Prevention: Tests and Guardrails

### 1. Backtest Metric Validation Test

```python
def test_no_hardcoded_metrics():
    """Ensure hooks don't contain hardcoded performance claims."""
    with open('.claude/hooks/inject_trading_context.sh') as f:
        content = f.read()

    # These should never be hardcoded
    assert "2.18 Sharpe" not in content
    assert "62.2% win rate" not in content

    # Should reference actual data
    assert "latest_summary.json" in content or "dynamic" in content.lower()
```

### 2. Size Multiplier Sanity Check

```python
def test_fear_multiplier_not_increasing():
    """Ensure fear conditions don't INCREASE position size."""
    from src.utils.fear_greed_index import FearGreedIndex

    fgi = FearGreedIndex()
    signal = fgi.get_trading_signal_for_value(20)  # Extreme fear

    # Should NOT increase position during fear
    assert signal["size_multiplier"] <= 1.0
    assert signal["action"] != "BUY"  # Should wait for confirmation
```

### 3. Strategy Win Rate Gate

```python
def test_strategy_minimum_win_rate():
    """Block strategies with <45% win rate from production."""
    from data.backtests.latest_summary import get_aggregate_metrics

    metrics = get_aggregate_metrics()

    # If win rate falls below 45%, strategy should be quarantined
    assert metrics["min_win_rate"] >= 45.0, "Strategy win rate too low for production"
```

### 4. Live P/L Circuit Breaker

```python
def test_pl_circuit_breaker():
    """Halt trading if P/L drops more than 1% in a week."""
    from data.performance_log import get_weekly_change

    weekly_change = get_weekly_change()

    if weekly_change < -1.0:
        raise CircuitBreakerTriggered(
            f"Weekly P/L {weekly_change}% exceeds -1% threshold. "
            "Trading halted for review."
        )
```

## Behavioral Finance Lessons

### Why Retail Traders Fail at Contrarian Timing

1. **Fear can persist**: FGI at 20 doesn't mean bottom - can go to 10
2. **Trend following wins**: Research shows 12.5% success for swing traders vs 5% for day traders
3. **Buy strength, not weakness**: Buying during uptrends (+5%) has better odds than buying dips (-5%)
4. **97% of day traders lose**: The "buy the dip" mentality is why

### The Correct Mental Model

```
WRONG: "Market is fearful, this is a buying opportunity!"
RIGHT: "Market is fearful, fear can persist. Wait for trend confirmation."

WRONG: "BTC is down 5%, buy more to average down!"
RIGHT: "BTC is down 5%, reduce exposure until trend reverses."
```

## Checklist for Future Strategy Changes

Before deploying any strategy change:

- [ ] Does it increase position size during adverse conditions? (RED FLAG)
- [ ] Is it based on backtested data or wishful thinking?
- [ ] What's the win rate in the WORST scenario, not the best?
- [ ] Does it match what research says works for retail traders?
- [ ] Are metrics shown to users derived from actual data, not hardcoded?
- [ ] Is there a circuit breaker if it starts losing?

## Related Lessons

- `ll_016_regime_pivot_safety_gates_dec12.md` - Safety gate architecture
- `ll_011_facts_benchmark_factuality_ceiling.md` - Fact-checking systems
- `ll_012_deep_research_safety_improvements_dec11.md` - Research validation

## Tags

`#strategy` `#risk-management` `#behavioral-finance` `#fear-greed` `#data-integrity` `#circuit-breaker` `#critical-failure`

---

*Generated: December 15, 2025*
*Author: Claude (CTO)*
*PR: #654 - Merged*
