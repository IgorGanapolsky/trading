---
layout: post
title: "Lesson Learned: Credit Spreads for Capital-Efficient Options Trading"
date: 2025-12-17
---

# Lesson Learned: Credit Spreads for Capital-Efficient Options Trading

**Date**: 2025-12-17
**Severity**: CRITICAL
**Category**: Options Strategy, Capital Management

## Problem Statement

Cash-Secured Puts (CSPs) require FULL collateral equal to strike price × 100 shares:
- SOFI $25 put requires $2,500 collateral
- SPY $650 put requires $65,000 collateral

With 19 equity positions consuming buying power, our OPTIONS buying power dropped to $153 - not enough for ANY cash-secured puts, even on cheap stocks.

## Root Cause Analysis

1. **All capital deployed to equities**: 19 positions using all available margin
2. **No cash reservation**: System deployed 100% of buying power to stocks
3. **Options buying power separate from buying power**: Alpaca has separate "options_buying_power"
4. **CSP collateral requirements**: Full strike × 100 needed per contract

## Solution Implemented

### 1. Credit Spreads (Bull Put Spreads)
- **Collateral = Spread Width × 100** (NOT full strike price!)
- $2 wide spread = $200 collateral (vs $2,500 for CSP)
- 10x+ more capital efficient
- Still collect premium (though less than naked CSP)

### 2. Adaptive Strategy Selection
```python
if options_buying_power < 1000:
    use_credit_spreads()  # $200-500 collateral per spread
else:
    use_cash_secured_puts()  # $1k-65k collateral per CSP
```

### 3. New Script: execute_credit_spread.py
- Bull put spread finder
- Automatic spread width calculation
- Same IV/trend filters as CSPs
- Integrated fallback in execute_options_trade.py

## Key Metrics

| Strategy | SOFI Collateral | SPY Collateral | Min Buying Power Needed |
|----------|-----------------|----------------|-------------------------|
| CSP | $2,500 | $65,000 | $1,000+ |
| $2 Credit Spread | $200 | $200 | $200 |
| $5 Credit Spread | $500 | $500 | $500 |

## Prevention Rules

1. **ALWAYS check options_buying_power before attempting CSPs**
2. **Adaptive strategy**: Use spreads when buying power < $1,000
3. **Consider reserving cash**: Don't deploy 100% to equities
4. **Monitor position count**: 19+ positions = likely low options BP

## Files Changed

- `scripts/execute_credit_spread.py` - NEW: Bull put spread execution
- `scripts/execute_options_trade.py` - Added spread fallback on insufficient BP
- `.github/workflows/daily-trading.yml` - Smart strategy selection

## Testing

Run manually:
```bash
python3 scripts/execute_credit_spread.py --symbol SOFI --width 2 --dry-run
```

## References

- Alpaca Options API: https://alpaca.markets/docs/trading/options/
- Bull Put Spreads: Max loss = width - credit received
- TastyTrade: Spreads are capital-efficient but have lower max profit

