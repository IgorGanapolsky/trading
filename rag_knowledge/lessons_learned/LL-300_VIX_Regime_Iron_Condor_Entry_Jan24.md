# LL-300: VIX Regime Guidelines for Iron Condor Entry

**Date**: January 24, 2026
**Category**: Strategy, Entry Timing, Volatility
**Severity**: MEDIUM (affects win rate)
**Status**: Research Complete

## Executive Summary

VIX levels significantly impact iron condor success rates. Research suggests optimal entry when VIX is 14-17 (calm but not too calm), avoiding entries when VIX > 18.

## VIX Regime Guidelines

| VIX Range | Market Mood | Iron Condor Recommendation |
|-----------|-------------|---------------------------|
| < 13 | Very calm | **Wait** - premiums too low |
| 14-17 | Optimal | **Enter** - best risk/reward |
| 15-25 | Acceptable | Good premiums, manageable risk |
| > 18 | Elevated | **Caution** - range may break |
| > 25 | High | **Avoid** - too volatile |

## Entry Timing Rules

### When to Enter
1. **VIX between 14-17** (sweet spot)
2. **No major events** in next 30 days (FOMC, CPI, earnings)
3. **SPY in established range** (not trending strongly)
4. **30-45 DTE** for optimal theta decay

### When to Avoid
1. **VIX > 18** - signals trouble ahead, range likely to break
2. **VIX < 13** - premiums too small, not worth the risk
3. **Day before/after FOMC** - volatility crush/expansion
4. **Major earnings weeks** (big tech, banks)

## Why VIX Matters for Iron Condors

**High VIX (>18):**
- Higher premiums (looks attractive)
- BUT: Higher probability of range breakout
- More likely to hit short strikes
- Win rate drops significantly

**Low VIX (<13):**
- Very small premiums
- Not worth the capital risk
- Win rate technically high but profit too small

**Optimal VIX (14-17):**
- Decent premium collection
- Lower probability of breakout
- Best risk-adjusted returns

## Practical Implementation

### Pre-Trade Checklist Addition
```python
def check_vix_regime():
    vix = get_current_vix()
    if vix < 13:
        return False, "VIX too low - premiums insufficient"
    if vix > 20:
        return False, "VIX too high - range may break"
    return True, f"VIX at {vix} - acceptable for entry"
```

### Suggested Integration
1. Add VIX check to pre-trade gate
2. Log VIX at entry for post-trade analysis
3. Track win rate by VIX regime over time

## Current SPY Context (Jan 2026)

- SPY trading around $690
- VIX typically 14-17 range
- Markets relatively calm post-election
- Good environment for iron condors

## ML Enhancement Opportunity

Future work could include:
1. Train classifier on historical iron condor outcomes
2. Features: VIX, VIX term structure, GEX, put/call ratio
3. Predict probability of range break before entry
4. Auto-adjust delta selection based on regime

## Sources

- [TradeStation - Iron Condor Strategy](https://www.tradestation.com/insights/2025/10/28/iron-condor-strategy-for-trading-neutral-markets-tradestation/)
- [Option Alpha - Iron Condor Guide](https://optionalpha.com/strategies/iron-condor)
- [CBOE - Zero-Day SPX Iron Condor](https://www.cboe.com/insights/posts/henry-schwartzs-zero-day-spx-iron-condor-strategy-a-deep-dive/)
- [AI Flow Trader - Volatility Regimes](https://www.aiflowtrader.com/blog/profiting-from-volatility-regime-changes-a-2025-st-2025-10)

## Tags
vix, iron_condor, entry_timing, volatility_regime, risk_management

---

*Researched January 24, 2026. Entry timing is one component - always follow full pre-trade checklist.*
