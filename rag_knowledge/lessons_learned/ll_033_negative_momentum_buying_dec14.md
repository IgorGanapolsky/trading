# LL-033: Stop Buying Crypto in Downtrends

**Date**: 2025-12-14
**Severity**: HIGH
**Category**: Strategy Bug
**Status**: FIXED

## Incident Summary

Crypto strategy was buying into falling markets, resulting in 100% loss rate on crypto trades (3 losses, 0 wins). The system selected the "best" performer even when ALL cryptos had negative 7-day momentum.

## Root Cause

```python
# BROKEN LOGIC:
best = max(analysis.items(), key=lambda x: x[1]["change_7d"])
# When all cryptos are negative, this picks the LEAST BAD one
# Example: BTC -2.15%, ETH -1.54%, SOL -2.51%
# System picked ETH at -1.54% (still negative = falling knife!)
```

## Impact

- **Crypto P/L**: -$0.43 (3 trades, all losses)
- **Win Rate**: 0% on crypto (was falsely reported as 100%)
- **Capital at Risk**: Continued buying into downtrends

## Fix Applied

1. **Momentum Threshold Filter**: Skip trade if best performer has negative momentum
2. **Extreme Fear Override**: If Fear & Greed <= 25, allow contrarian buying (historically oversold)
3. **Win Rate Calculation**: Fixed math error (4 wins / 8 trades = 50%, not 100%)

## Code Changes

**Files Modified**:
- `.github/workflows/force-crypto-trade.yml` (lines 178-192)
- `.github/workflows/weekend-crypto-trading.yml` (lines 205-214)
- `data/system_state.json` (performance metrics)

**New Logic**:
```python
if best_momentum < 0:
    if fear_greed_index <= 25:  # Extreme Fear = oversold = BUY
        print("🔥 EXTREME FEAR OVERRIDE: Contrarian buy!")
        result["contrarian_buy"] = True
    else:
        print("⛔ SKIP: All cryptos in downtrend")
        result["action"] = "SKIP"
        sys.exit(0)
```

## Prevention Measures

1. **Pre-Trade Validation**: Always check if selected asset has positive momentum
2. **Contrarian Strategy**: Only buy negative momentum during Extreme Fear (historical oversold)
3. **Win Rate Audit**: Validate metrics against actual closed_trades array
4. **State Freshness**: Alert if system_state.json > 24 hours stale

## Verification Tests Needed

- [ ] Unit test: `test_momentum_filter_blocks_negative()`
- [ ] Unit test: `test_extreme_fear_override_works()`
- [ ] Integration test: `test_win_rate_calculation_accuracy()`
- [ ] E2E test: `test_crypto_trade_only_positive_momentum()`

## Related Lessons

- LL-029: Always verify date before reporting
- LL-019: Trading system dead for 2 days (staleness detection)
- LL-032: Crypto trades 24/7/365

## Tags

#crypto #momentum #strategy-bug #win-rate #verification
