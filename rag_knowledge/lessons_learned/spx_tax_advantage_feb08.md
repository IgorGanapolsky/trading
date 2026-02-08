# SPX Tax Advantage Over SPY (Feb 8, 2026)

## Source: CBOE, Green Trader Tax, IRS Publication 550

### The Problem
SPY options = equity options = 100% short-term capital gains tax.
To net $6,000/month after-tax at ~37% marginal rate, need ~$9,500/month pre-tax.

### The Solution: SPX/XSP Section 1256
SPX options qualify for Section 1256 60/40 tax treatment:
- 60% taxed as long-term capital gains (max 20%)
- 40% taxed as short-term capital gains (max 37%)
- Blended effective rate: ~26.8% (vs ~37% for SPY)
- Regardless of holding period

### Dollar Impact
| Metric | SPY (equity) | SPX (Section 1256) |
|--------|-------------|-------------------|
| Tax rate | ~37% | ~26.8% |
| Pre-tax needed for $6K/mo | ~$9,524 | ~$8,197 |
| Annual tax savings | $0 | ~$15,924 |

### Action Required
1. Add SPX/XSP to ALLOWED_TICKERS in trading_constants.py
2. Update options_executor.py for index option differences (cash-settled, European-style, no early assignment)
3. File Form 6781 for Section 1256 contracts at tax time
4. XSP = mini-SPX (1/10th notional) — better for $100K account sizing

### Caveats
- SPX has wider bid-ask spreads than SPY
- XSP (mini-SPX) has better sizing for smaller accounts but less liquidity
- Cash-settled (no stock assignment risk — this is actually an advantage)
- European-style exercise only (no early assignment — also an advantage)
