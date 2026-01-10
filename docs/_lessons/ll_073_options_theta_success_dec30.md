---
layout: post
title: "Lesson Learned #073: Options Theta Strategy Delivering 99% of Profits"
date: 2025-12-30
---

# Lesson Learned #073: Options Theta Strategy Delivering 99% of Profits

**Date**: December 30, 2025 (Day 50/90)
**Severity**: HIGH
**Category**: Strategy Success

## Summary

On Day 50 of the 90-day challenge, options positions account for 99% of total profits (+$932 out of +$942.23). This validates our Phil Town-inspired concentration strategy.

## What's Working

### 1. Short Put Strategy
Selling puts on quality underlyings generates consistent theta income:
- SPY 660 Put: +$460.00
- AMD 200 Put: +$322.00
- INTC 35 Puts: +$105.00 (2 contracts)
- SOFI 24 Put: +$45.00

### 2. Theta Decay
As option sellers, time decay works in our favor. Every passing day erodes option value, benefiting our short positions.

### 3. Phil Town Concentration
We're focused on a few high-quality underlyings rather than over-diversifying:
- SPY (market index - core holding)
- AMD (semiconductor leader)
- INTC (value play at support)
- SOFI (fintech with growth potential)

### 4. Strike Selection Discipline
- SPY 660: ~5% OTM (safe margin)
- AMD 200: Deep OTM
- INTC 35: At historical support

## What's NOT Working

### 1. Pure Equity Exposure
SPY shares contributed only +$113.95 (1% of profits) while options contributed +$932 (99%).

### 2. Automation Reliability
GitHub Actions workflow failed due to secrets validation. Manual screenshot audit was required.

## Financial Evidence
- Portfolio: $100,942.23
- Total P/L: +$942.23 (+0.94%)
- Options P/L: +$932.00 (99%)
- Equity P/L: +$113.95 (1%)

## Recommendations

1. **Increase options allocation** - They're generating 99% of profits
2. **Reduce pure equity exposure** - Lower ROI compared to options
3. **Fix automation** - Ensure daily sync works reliably
4. **Monitor VIX** - High volatility could hurt short put positions

## Prevention/Next Steps

- Continue short put strategy on quality underlyings
- Target 30-45 DTE for optimal theta decay
- Size positions appropriately (no single position >5% of account)
- Review and potentially trim equity exposure

## Tags
`options` `theta` `short-puts` `phil-town` `success` `strategy`
