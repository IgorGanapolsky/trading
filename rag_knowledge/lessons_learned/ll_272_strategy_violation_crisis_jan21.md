# LL-272: Strategy Violation Crisis - Multiple Rogue Workflows

**Date**: 2026-01-21
**Category**: Trading, Strategy, Compliance
**Severity**: CRITICAL (until fixed), then RESOLVED

## Summary

On Jan 21, 2026, the trading system LOST $70.13 due to executing trades that VIOLATE CLAUDE.md strategy mandate. The system bought SPY SHARES and SOFI OPTIONS when it should ONLY execute iron condors on SPY.

## Evidence

From Alpaca dashboard (Jan 21, 2026):
- Portfolio: $5,028.84 (-1.38%)
- Daily Change: **-$70.13 LOSS**

From system_state.json trade_history (Jan 21, 2026):
```
16:17:51 - SPY Market BUY 0.146092795 @ $684.428  <- WRONG (shares, not options)
16:17:19 - SPY Market BUY 0.146103469 @ $684.378  <- WRONG (shares, not options)
16:08:46 - SPY Market BUY 1 @ $684.18            <- WRONG (shares, not options)
14:48:16 - SOFI260213P00032000 BUY 1 @ $7.30     <- WRONG (SOFI, not SPY)
```

Current non-compliant positions:
```
SPY: 2.439018421 shares @ $683.99 = $1,668.26   <- SHOULD BE $0 (options only)
```

## Root Causes

### 1. daily-voo-dca.yml Running on Schedule
- **Cron**: `'0 14,15 * * 1-5'` (10:00 AM ET every weekday)
- **Action**: Buys VOO/SPY SHARES via dollar-cost averaging
- **Violation**: CLAUDE.md says "Primary strategy: IRON CONDORS on SPY ONLY"
- **Impact**: ~$1,668 in SPY shares accumulated

### 2. emergency-simple-trade.yml With SOFI Default
- **Default Symbol**: "SOFI" (non-whitelisted ticker)
- **Action**: Buys shares of any symbol on manual trigger
- **Violation**: CLAUDE.md says "NO individual stocks. The $100K success was SPY. The $5K failure was SOFI."
- **Impact**: SOFI option purchase at $730 ($7.30 x 100)

### 3. Insufficient Enforcement
- While iron_condor_trader.py has SPY-only validation via ticker_validator.py
- Other workflows bypass the validation entirely
- No system-wide enforcement of strategy compliance

## Impact

- **Financial**: -$70.13 loss on Jan 21
- **Capital tied up**: $1,668 in SPY shares not available for iron condors
- **Strategy drift**: System not executing defined strategy
- **Trust erosion**: CEO losing confidence in system reliability

## Fix Implemented (Jan 21, 2026)

### 1. Disabled daily-voo-dca.yml
```yaml
# DISABLED: Schedule removed - no stock buying allowed
# schedule:
#   - cron: '0 14,15 * * 1-5'
```

### 2. Disabled emergency-simple-trade.yml
- Changed default symbol from SOFI to SPY
- Added warn-disabled job that always fails
- Added `if: false` double protection on trade job

### 3. Created liquidate_non_compliant_positions.py
- Script to sell all stock positions
- Script to close all non-SPY options
- Dry-run mode for preview

### 4. Ticker Validator Already Enforces SPY-Only
- `/src/utils/ticker_validator.py` - whitelist = {"SPY"}
- `iron_condor_trader.py` calls validate_ticker() before trading

## Prevention

1. **CI check**: Add workflow that scans for scheduled jobs buying non-options
2. **Audit**: Review all workflows for strategy compliance monthly
3. **Single trader**: Only iron_condor_trader.py should execute trades
4. **Hard blocks**: All new trading code must use ticker_validator.py

## CLAUDE.md Strategy (For Reference)

Per CLAUDE.md (Jan 19, 2026):
- "Primary strategy: IRON CONDORS on SPY ONLY - defined risk on BOTH sides"
- "NO individual stocks. The $100K success was SPY. The $5K failure was SOFI."
- "Position limit: 1 iron condor at a time (5% max = $248 risk)"

## Next Steps

1. Run `python3 scripts/liquidate_non_compliant_positions.py` during market hours
2. Monitor that only iron_condor_trader.py executes trades
3. Re-execute iron condor strategy once capital is freed

## Phil Town Alignment

This violates Rule #1: "Don't Lose Money"
- Buying SPY shares is not iron condor strategy
- SOFI trades repeat the $5K failure pattern
- System must be disciplined to ONE strategy

## Tags

`critical`, `strategy-violation`, `iron-condor`, `compliance`, `workflow`, `rule-1`, `fix-jan21`
