---
layout: post
title: "Day 74: Strategy Pivot - CSPs to Credit Spreads"
date: 2026-01-13
categories: [trading, strategy, options]
---

## The Problem

With $5K capital, Cash-Secured Puts (CSPs) were limiting our growth:
- Each CSP requires ~$2,400 collateral
- Max 2 CSPs at a time
- Max daily income: ~$20/day
- North Star ($100/day): **UNREACHABLE**

## The Solution: Credit Spreads

Bull Put Spreads provide 10x capital efficiency:

| Metric | CSP | Credit Spread |
|--------|-----|---------------|
| Collateral | $2,400 | $500 |
| Max positions | 2 | 10 |
| Weekly income | $100 | $1,000 |
| Daily income | $20 | **$200** |

## How It Works

1. **Sell ATM put** - Collect premium
2. **Buy OTM put** - Define max loss
3. **$5 wide spread** = $500 collateral
4. **~$100 premium** per spread

## Technical Implementation

Created `execute-credit-spread.yml` workflow:
- Dynamic strike selection based on current price
- Queries Alpaca option chain API
- Finds ATM strikes automatically
- Handles edge cases

## Today's Results

- Portfolio: $5,018.25 (+$18.25, +0.36%)
- Put position closed with +$11 profit
- Workflow ready for tomorrow's trade

## Key Lessons (LL-179, LL-180)

1. Don't use hardcoded strikes - query actual options
2. Credit spreads unlock capital efficiency
3. $5K IS sufficient for $100/day goal

## Next Steps

Tomorrow (Jan 14, 9:35 AM ET):
- Execute first credit spread on SOFI
- Target: 1 spread, $5 wide, ~$100 premium

The math now works. Ready to compound.
