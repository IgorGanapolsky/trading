# LL-296: XSP Tax Optimization Recommendation

**Date**: January 23, 2026
**Category**: Tax Optimization / Strategy
**Severity**: HIGH (CEO Decision Required)
**Related**: LL-295 (Four Pillars of Wealth Building)

## Executive Summary

Research indicates switching from SPY to XSP (Mini-SPX) iron condors could save **~30% on taxes** through Section 1256 60/40 treatment, adding **$15,000-20,000** to the account over 7 years.

## Current State

- **Strategy**: SPY iron condors only (per CLAUDE.md)
- **Tax treatment**: 100% short-term capital gains (~32% tax rate)
- **Account**: $30,000

## Proposed Change

Switch from SPY to **XSP (Mini-SPX)** iron condors.

## Why XSP vs SPX?

| Feature | SPY | XSP | SPX |
|---------|-----|-----|-----|
| Contract value | ~$590 | ~$590 | ~$5,900 |
| Position size for $30K | ✅ Fits | ✅ Fits | ❌ Too large |
| Tax treatment | Short-term | **60/40** | **60/40** |
| Assignment risk | Yes (American) | **No (European)** | **No (European)** |
| Cash settled | No | **Yes** | **Yes** |
| Wash sale rules | Apply | **Don't apply** | **Don't apply** |

**XSP is ideal for $30K account** - same size as SPY, better tax treatment.

## Tax Math (Section 1256)

```
SPY (short-term only):
  $10,000 gains × 32% = $3,200 tax

XSP (60/40 treatment):
  $6,000 (60%) × 15% long-term = $900
  $4,000 (40%) × 32% short-term = $1,280
  Total: $2,180 tax

Savings: $1,020 (31.9%)
```

## 7-Year Projection

| Year | Pre-Tax Gains | SPY Tax | XSP Tax | Cumulative Savings |
|------|---------------|---------|---------|-------------------|
| 1 | $5,400 | $1,728 | $1,210 | $518 |
| 2 | $7,900 | $2,528 | $1,770 | $1,276 |
| 3 | $11,600 | $3,712 | $2,598 | $2,390 |
| 5 | $25,000 | $8,000 | $5,600 | ~$5,000 |
| 7 | $50,000+ | $16,000 | $11,200 | **~$15,000-20,000** |

## Risk Considerations

1. **Liquidity**: XSP less liquid than SPY (wider bid-ask spreads)
2. **Fills**: May get slightly worse fills
3. **Learning curve**: Different option chain structure
4. **Broker support**: Verify TastyTrade supports XSP

## Recommendation

**Phase 1 (Paper Trading)**: Test XSP iron condors alongside SPY for 30 days
**Phase 2 (Small Live)**: If fills acceptable, switch 50% of trades to XSP
**Phase 3 (Full Migration)**: If Phase 2 successful, fully migrate to XSP

## Implementation Steps

1. [ ] CEO approves XSP testing
2. [ ] Add XSP to paper trading watchlist
3. [ ] Compare XSP vs SPY bid-ask spreads
4. [ ] Run parallel paper trades for 30 days
5. [ ] Analyze fill quality and slippage
6. [ ] Update CLAUDE.md strategy if approved

## Infrastructure Ready

The `iron_condor_backtester.py` already supports XSP:
```bash
python scripts/backtest/iron_condor_backtester.py --ticker XSP --days 90
```

## Sources

- [CBOE XSP Tax Benefit](https://www.cboe.com/tradable_products/sp_500/mini_spx_options/tax_benefit/)
- [Section 1256 Contracts](https://www.irs.gov/forms-pubs/about-form-6781)
- [Green Trader Tax](https://greentradertax.com/trading-futures-other-section-1256-contracts-has-tax-advantages/)

## Tags

`tax-optimization`, `XSP`, `SPX`, `Section-1256`, `60-40`, `strategy`
