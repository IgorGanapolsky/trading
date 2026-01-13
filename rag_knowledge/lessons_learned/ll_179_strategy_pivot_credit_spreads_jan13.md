# LL-179: Strategy Pivot - CSPs to Credit Spreads

**Date:** January 13, 2026
**Session:** 9

## Problem
- CSPs require $2,400 collateral each
- $5K capital = only 2 CSPs max
- Max daily income: ~$20/day
- North Star ($100/day) unreachable with CSPs

## Solution: Credit Spreads
- Bull put spreads: Sell ATM put, buy $5 OTM put
- Collateral: $500 per spread (vs $2,400 for CSP)
- Premium: ~$100 per spread
- $5K capital = 10 spreads max
- Max weekly income: $1,000 = $200/day

## Math Comparison
| Metric | CSP | Credit Spread |
|--------|-----|---------------|
| Collateral | $2,400 | $500 |
| Max positions | 2 | 10 |
| Weekly income | $100 | $1,000 |
| Daily income | $20 | $200 |

## Risk Management
- Max loss per spread: $400 (spread width - premium)
- Stop-loss: 25% loss ($25)
- Never >5% account on single trade
- Use defined-risk strategies only

## Sources
- [Alpaca: Credit Spreads](https://alpaca.markets/learn/credit-spreads)
- [Option Alpha: 0DTE Performance](https://optionalpha.com/blog/0dte-options-strategy-performance)
- [Schwab: Credit Put Spread](https://www.schwab.com/learn/story/reducing-risk-with-credit-spread-options-strategy)

## Action Items
1. Update trading workflow to execute credit spreads
2. Implement spread order logic in Alpaca
3. Test with paper trading
4. Scale to 5-10 spreads per week
