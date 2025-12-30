---
lesson_id: LL-053
title: "Options Theta Strategy Delivering 99% of Profits"
date: 2025-12-30
category: strategy
severity: success
tags: [options, theta, phil-town, short-puts]
---

# Lesson Learned #053: Options Theta Strategy Success

## Summary
On Day 50 of the 90-day challenge, options positions account for 99% of total profits (+$932 out of +$942).

## Key Findings

### What's Working
1. **Short Put Strategy**: Selling puts on quality underlyings (SPY, AMD, INTC, SOFI)
2. **Theta Decay**: Time is our friend as option sellers
3. **Phil Town Concentration**: Focus on few high-quality positions
4. **Strike Selection**: OTM puts with 30-45 DTE

### Performance Breakdown
| Position | P/L | Strategy |
|----------|-----|----------|
| SPY 660 Put | +$460 | Short put |
| AMD 200 Put | +$322 | Short put |
| INTC 35 Puts | +$105 | Short puts (2x) |
| SOFI 24 Put | +$45 | Short put |
| SPY Shares | +$114 | Core equity |

### What's NOT Working
1. **Equity positions**: Only +$114 from SPY shares vs +$932 from options
2. **Automation**: GitHub Actions failed - needed manual screenshot audit
3. **Data freshness**: System state went stale

## Root Cause Analysis
- Options provide leverage without margin risk (cash-secured)
- Theta decay is predictable and consistent
- Market staying range-bound benefits put sellers

## Recommendations
1. **Increase options allocation**: Currently generating 99% of profits
2. **Reduce pure equity exposure**: Lower ROI than options
3. **Fix automation**: Ensure daily sync works without manual intervention
4. **Monitor volatility**: VIX spikes could hurt short put positions

## Evidence
- Portfolio: $100,942.23
- Total P/L: +$942.23 (+0.94%)
- Options P/L: +$932 (99% of total)
- Source: Live Alpaca screenshot Dec 30, 10:28 AM EST

## Tags
#options #theta #short-puts #phil-town #success #day-50
