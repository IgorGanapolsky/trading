# LL-040: Catching Falling Knives - Trend Confirmation Required

**Date**: December 15, 2025
**Severity**: HIGH
**Category**: Trading Strategy
**Status**: RESOLVED

## Problem

Our crypto trading strategy was buying during "extreme fear" periods without confirming the price trend, resulting in losses from catching falling knives.

### What Happened
- Strategy v3.0 bought when Fear & Greed Index < 25 (contrarian buy)
- Did NOT check if price was in a downtrend
- Result: Bought BTC/ETH while prices were falling
- Loss: -$96 overall portfolio

### Root Cause
1. **Fear & Greed alone is not enough** - It's a sentiment indicator, not a timing indicator
2. **Missing trend confirmation** - Buying during fear without checking if trend has reversed
3. **Catching falling knives** - Buying into a downtrend hoping for reversal

## Solution

### v4.0 Fix (Partial)
- Added 50-day Moving Average filter
- Only buy when price > 50-day MA
- Research: 5x better returns per Coinbase study

### v4.1 Fix (Complete)
- Added RSI > 50 confirmation
- Only buy when:
  1. Price > 50-day MA (trend up)
  2. RSI > 50 (momentum bullish)
- Skip reason differentiates MA vs RSI failures

## Implementation

```python
# v4.1 Strategy Logic
def calc_rsi(prices, period=14):
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# Entry conditions
above_ma = price > ma50  # Trend filter
rsi_bullish = rsi > 50   # Momentum filter
valid_entry = above_ma AND rsi_bullish
```

## Research Basis

1. **Coinbase Research**: Trend-aware DCA (only buy above 50-day MA) = 5x better returns
2. **RSI Momentum**: RSI > 50 confirms momentum is bullish, not just price
3. **Fear & Greed**: Use for SIZING only (1.5x in extreme fear), NOT for timing

## Prevention Checklist

- [ ] Never buy based on sentiment alone (Fear & Greed)
- [ ] Always confirm trend (price > MA)
- [ ] Always confirm momentum (RSI > 50)
- [ ] Use sentiment for position sizing, not entry timing
- [ ] Backtest any strategy change before deployment

## Files Changed

- `.github/workflows/force-crypto-trade.yml` - v4.1 with RSI
- `.github/workflows/weekend-crypto-trading.yml` - v4.1 with RSI

## Related PRs

- PR #649: feat: Crypto Strategy v4.1 - RSI momentum confirmation

## Verification Tests Needed

1. **Unit Test**: RSI calculation accuracy
2. **Integration Test**: Entry signal requires both MA + RSI
3. **Backtest**: v4.1 vs v3.0 performance comparison
4. **CI Check**: Workflow syntax validation before merge

## Tags

`trading-strategy` `crypto` `risk-management` `trend-following` `rsi` `moving-average`
