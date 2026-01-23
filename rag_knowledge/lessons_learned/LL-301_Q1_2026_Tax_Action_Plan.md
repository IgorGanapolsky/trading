# LL-301: Q1 2026 Tax Action Plan

**Date**: January 23, 2026
**Category**: Tax Strategy / Action Items
**Severity**: HIGH
**Related**: LL-296, LL-297, LL-294

## Executive Summary

Concrete action items for Q1 2026 tax planning. This is the "do this now" version of the comprehensive tax strategy (LL-297).

## Immediate Actions (This Week)

### 1. Alpaca Inquiry Response
Email Braxton at AlpacaDB with:
```
Subject: XSP Options Support & Tax Optimization

Hi Braxton,

Thanks for following up. Here's what I'm evaluating:

1. Does Alpaca support XSP (Mini-SPX) options trading?
   - Seeking Section 1256 tax treatment (60/40)
   - Same contract size as SPY but better tax efficiency

2. What tax lot accounting methods are available?
   - Need Specific Identification for optimization

3. How is Form 6781 data provided for Section 1256 contracts?

My strategy: Iron condors for income, optimizing for after-tax returns
Goal: $6K/month after-tax income within 3 years

Best,
Igor
```

### 2. Tax Tracking Setup
- [ ] Create spreadsheet for 2026 trade tracking
- [ ] Columns: Date, Underlying, Open/Close, Credit/Debit, P/L, Wash Sale Flag
- [ ] Track cost basis per position
- [ ] Note: System already tracks in `data/system_state.json -> trade_history`

### 3. Quarterly Estimated Tax Reserve
- Current Q1 profits: $0 (fresh start Jan 22)
- Reserve 30% of profits monthly
- Q1 payment due: April 15, 2026

## Decision: SPY vs XSP

Based on LL-297 analysis:

| Account Size | Projected Annual Gains | Recommendation |
|--------------|----------------------|----------------|
| $30K (current) | ~$5K | **SPY** (liquidity > tax savings) |
| $50K | ~$8K | SPY (still below breakeven) |
| $75K+ | ~$16K+ | **Switch to XSP** |

**Current Recommendation**: Stay with SPY until account exceeds $75K.

## Q1 2026 Milestones

| Date | Action | Status |
|------|--------|--------|
| Jan 23 | Create tax tracking sheet | [ ] |
| Jan 31 | Review first week paper trades | [ ] |
| Feb 15 | Mid-Q1 profit review | [ ] |
| Mar 15 | Q1 pre-close review | [ ] |
| Apr 15 | Q1 estimated tax payment | [ ] |

## Monthly Tax Reserve Calculation

```python
# Monthly tax reserve formula
def calculate_reserve(monthly_pnl: float, tax_rate: float = 0.30) -> float:
    """Reserve 30% of net profits for estimated taxes."""
    if monthly_pnl <= 0:
        return 0.0  # No tax on losses
    return monthly_pnl * tax_rate

# Example: $500 profit in January
# Reserve: $500 * 0.30 = $150 set aside
```

## Tax-Loss Harvesting Opportunities

If any position shows a loss:
1. **Before Dec 31**: Close and realize loss
2. **Wash sale avoidance**: Either wait 31 days OR switch to XSP
3. **Note**: Losses offset gains dollar-for-dollar

## Key Tax Numbers for 2026

| Item | Amount |
|------|--------|
| Starting capital | $30,000 |
| Target annual return | 8% monthly compounded |
| Projected Year 1 gains | ~$5,400 |
| Tax at 32% (SPY) | $1,728 |
| Tax at 22% (XSP) | $1,188 |
| Savings if XSP | $540 |

**Verdict**: $540 savings < $1,600 extra slippage = **Stay with SPY for Year 1**

## Automation Ideas (Future)

1. Auto-calculate tax reserve after each trade close
2. Alert when account crosses XSP breakeven threshold ($75K)
3. Wash sale tracking and warning system
4. Quarterly tax payment reminder workflow

## Sources

- LL-297: Comprehensive Tax Strategy Planning
- LL-296: XSP Tax Optimization Recommendation
- IRS Estimated Tax Guidelines
- Alpaca Cost Basis Documentation

## Tags

`tax-2026`, `Q1-action-plan`, `estimated-taxes`, `SPY`, `action-items`
