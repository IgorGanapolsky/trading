---
layout: post
title: "Lesson Learned #087: Critical Strategy Fixes (Jan 6, 2026)"
date: 2026-01-06
---

# Lesson Learned #087: Critical Strategy Fixes (Jan 6, 2026)

## Date
2026-01-06

## Category
STRATEGY_FIX

## Summary
Deep investigation revealed multiple critical flaws causing -3.04% avg daily return despite 80% win rate claim.

## Root Causes Found

### 1. MACD Calculation Wrong
- **Bug**: `signal_line = macd_line * 0.9` (arbitrary multiplier)
- **Fix**: Proper 9-period EMA of MACD values
- **Impact**: Eliminated false crossover signals

### 2. R:R Ratio Too Low
- **Bug**: 4% take profit / 2% stop loss = 2:1 R:R
- **Fix**: 6% take profit / 2% stop loss = 3:1 R:R
- **Impact**: At 25% win rate: -0.5% → 0% (break-even)
- **Impact**: At 40% win rate: -0.2% → +1.2% per trade

### 3. Slippage Disabled in Backtests
- **Bug**: `slippage_model_enabled: False`
- **Fix**: `slippage_model_enabled: True`
- **Impact**: Backtests now show realistic returns

### 4. Dishonest Metrics
- **Bug**: Claimed 80% win rate on only 5 trades
- **Fix**: Added `win_rate_sample_size` and warnings
- **Impact**: Honest reporting prevents false confidence

## Files Changed
- `src/strategies/core_strategy.py` - MACD fix, R:R fix
- `scripts/run_backtest_matrix.py` - Slippage enabled
- `src/utils/technical_indicators.py` - Series to float fix
- `data/system_state.json` - Honest metrics

## Prevention
- Always verify MACD uses proper signal line (9-EMA of MACD)
- R:R ratio must support expected win rate
- Backtests must include slippage
- Sample size must be disclosed for any statistical claim

## Tags
strategy, MACD, R:R, slippage, metrics, honesty
