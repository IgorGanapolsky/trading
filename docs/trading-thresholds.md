# Trading Signal Thresholds

**Last Updated**: December 10, 2025
**Status**: Tightened from R&D collection mode to production quality

## Current Thresholds

| Parameter | Value | Previous | Change Reason |
|-----------|-------|----------|---------------|
| ADX_MIN | **20.0** | 5.0 | Filter ranging markets (50% whipsaw rate) |
| MACD_THRESHOLD | **0.0** | -0.1 | Require confirmed bullish crossover |
| RSI_OVERBOUGHT | **65.0** | 75.0 | Avoid extreme overbought conditions |
| VOLUME_MIN | **1.0** | 0.6 | Require average+ volume for conviction |

## Why These Changes?

### Problem Identified (Dec 10, 2025)
- **0% live win rate** (only 1 trade ever closed, it was a loss)
- **Negative Sharpe ratios**: -7 to -2086 across all 13 backtest scenarios
- **Root cause**: Taking trades in ranging markets with unconfirmed signals

### ADX Regime Filter
| ADX Range | Market Type | Expected Win Rate | Action |
|-----------|-------------|-------------------|--------|
| 0-20 | Ranging/Trendless | 40-50% | ❌ REJECT |
| 20-40 | Trending | 55-65% | ✅ TRADE |
| 40+ | Strong Trend | 65-75% | ✅ TRADE (best) |

**Previous (5.0)**: Accepted ANY market, including completely flat/ranging
**New (20.0)**: Only trades in confirmed trending markets

### MACD Confirmation
| MACD Value | Signal | Previous Action | New Action |
|------------|--------|-----------------|------------|
| > 0.0 | Confirmed bullish | ✅ Accept | ✅ Accept |
| -0.1 to 0.0 | Near crossover | ✅ Accept | ❌ Reject |
| < -0.1 | Bearish | ❌ Reject | ❌ Reject |

**Problem**: Near-crossover signals (MACD between -0.1 and 0) fail ~55% of the time
**Fix**: Only accept confirmed bullish (MACD > 0)

### RSI Ceiling
| RSI Range | Condition | Previous | New |
|-----------|-----------|----------|-----|
| 0-30 | Oversold | ❌ | ❌ |
| 30-65 | Normal | ✅ | ✅ |
| 65-75 | Overbought | ✅ | ❌ |
| 75+ | Extreme | ❌ | ❌ |

**Problem**: RSI 65-75 is overbought territory with mean-reversion risk
**Fix**: Exit entry zone at 65 instead of 75

### Volume Confirmation
| Volume Ratio | Conviction | Previous | New |
|--------------|------------|----------|-----|
| < 0.6 | Very weak | ❌ | ❌ |
| 0.6-1.0 | Weak | ✅ | ❌ |
| 1.0-1.5 | Normal | ✅ | ✅ |
| > 1.5 | Strong | ✅ | ✅ |

**Problem**: 0.6x volume = 40% below average, weak conviction
**Fix**: Require at least average volume (1.0x)

## Environment Variables

Override defaults via environment:
```bash
export MOMENTUM_ADX_MIN=20.0
export MOMENTUM_MACD_THRESHOLD=0.0
export MOMENTUM_RSI_OVERBOUGHT=65.0
export MOMENTUM_VOLUME_MIN=1.0
```

## Expected Impact

| Metric | Before (R&D) | After (Dec 10) | Target |
|--------|--------------|----------------|--------|
| Trades/day | ~3-5 | ~1-2 | Quality over quantity |
| Win rate | 0% live | 55%+ | >55% |
| Sharpe | -7 to -72 | >0.5 | >1.0 |
| Signal quality | Low | High | Confirmed trends only |

## Code Location

Thresholds defined in:
- `src/strategies/legacy_momentum.py` (lines 47-60)
- `src/strategies/growth_strategy.py` (filter logic)
- `src/agents/signal_agent.py` (signal generation)

## History

| Date | Change | Rationale |
|------|--------|-----------|
| Dec 4, 2025 | Relaxed to -0.1/75/0.6/5.0 | Data collection for R&D |
| Dec 9, 2025 | ADX lowered to 5.0 | More trades through Gate 1 |
| Dec 10, 2025 | Tightened to 0.0/65/1.0/20.0 | Fix 0% win rate |
