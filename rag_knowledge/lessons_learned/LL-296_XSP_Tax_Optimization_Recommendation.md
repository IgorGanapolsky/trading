# LL-296: XSP Tax Optimization Recommendation

**Date**: January 23, 2026
**Category**: Tax Optimization / Strategy
**Severity**: HIGH (CEO Decision Required)
**Related**: LL-295 (Four Pillars of Wealth Building)

## CRITICAL: Alpaca Does NOT Support XSP/SPX

```
⚠️  BLOCKER: Alpaca only supports EQUITY options (SPY, stocks)
⚠️  Alpaca does NOT support INDEX options (SPX, XSP, NDX)
⚠️  This tax optimization REQUIRES A DIFFERENT BROKER
```

**Alternative brokers that support XSP/SPX:**
- TastyTrade (recommended for options)
- Interactive Brokers
- Schwab/TD Ameritrade
- Fidelity

**Alpaca Roadmap**: Index options planned for 2026, but not available yet.

---

## Executive Summary

Research indicates switching from SPY to XSP (Mini-SPX) iron condors could save **~30% on taxes** through Section 1256 60/40 treatment, adding **$15,000-20,000** to the account over 7 years.

**However, this requires a broker that supports index options (not Alpaca).**

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

1. **BROKER LIMITATION**: Alpaca does NOT support XSP/SPX - requires different broker
2. **Liquidity**: XSP less liquid than SPY (wider bid-ask spreads)
3. **Fills**: May get slightly worse fills
4. **Learning curve**: Different option chain structure
5. **Account management**: Would need to manage two broker accounts

## Recommendation

**Phase 1 (Paper Trading)**: Test XSP iron condors alongside SPY for 30 days
**Phase 2 (Small Live)**: If fills acceptable, switch 50% of trades to XSP
**Phase 3 (Full Migration)**: If Phase 2 successful, fully migrate to XSP

## Implementation Steps (Requires New Broker)

1. [ ] CEO decides if tax savings worth managing second broker
2. [ ] Open paper account at TastyTrade or IBKR
3. [ ] Test XSP iron condors on new broker
4. [ ] Compare XSP vs SPY bid-ask spreads
5. [ ] Run parallel paper trades for 30 days
6. [ ] If successful, allocate portion of capital to XSP broker

## Current Alpaca Strategy (No Change Needed)

Continue SPY iron condors on Alpaca:
- $30K account = no PDT restrictions ✅
- SPY has best liquidity ✅
- Tax treatment: 100% short-term (accept this for now)

## Backtester Note

The `iron_condor_backtester.py` supports XSP ticker for analysis, but **cannot execute trades** on Alpaca:
```bash
# For research/analysis only - Alpaca cannot trade XSP
python scripts/backtest/iron_condor_backtester.py --ticker XSP --days 90
```

## Sources

- [CBOE XSP Tax Benefit](https://www.cboe.com/tradable_products/sp_500/mini_spx_options/tax_benefit/)
- [Section 1256 Contracts](https://www.irs.gov/forms-pubs/about-form-6781)
- [Green Trader Tax](https://greentradertax.com/trading-futures-other-section-1256-contracts-has-tax-advantages/)
- [Alpaca Options Trading Docs](https://docs.alpaca.markets/docs/options-trading) - equity options only
- [Alpaca Forum: SPX Options Request](https://forum.alpaca.markets/t/spx-options-trading/16510) - not supported
- [GitHub Issue #265: Index Options](https://github.com/alpacahq/Alpaca-API/issues/265) - feature request

## Tags

`tax-optimization`, `XSP`, `SPX`, `Section-1256`, `60-40`, `strategy`
