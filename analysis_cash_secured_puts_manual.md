# Cash-Secured Put Analysis - Maximum Daily Options Income
**Date**: December 29, 2025
**Buying Power**: $2,487.77
**Strategy**: Phil Town Style Cash-Secured Puts
**Target**: 30-45 DTE, 20-30 Delta

---

## Current Stock Prices (December 2025)

| Ticker | Current Price | In $20-30 Range? | Notes |
|--------|--------------|------------------|-------|
| SOFI   | ~$30-32     | ✓ YES            | Recent ATH $32.73 (Nov 2025), very volatile |
| F      | $13.46      | ✗ NO (too low)   | Dividend yield 4.39% |
| BAC    | $53.57      | ✗ NO (too high)  | Strong financials, stable |
| PLTR   | $188.71     | ✗ NO (too high)  | Up 150%+ in 2025, very expensive |
| AMD    | $214.99     | ✗ NO (too high)  | Up 80% in 2025, AI boom |

**IMPORTANT**: Only SOFI and F are reasonably close to the $20-30 target range. The others (BAC, PLTR, AMD) are significantly more expensive and would require much more capital.

---

## Analysis: SOFI (Best Fit for Your Criteria)

**Current Price**: ~$30-32
**Stock Characteristics**: High growth fintech, very volatile (good for premium collection)

### Cash-Secured Put Setup (30-45 DTE, 0.25 delta)
- **Strike Price**: $28-29 (approximately 7-10% OTM)
- **Delta**: ~0.25 (25% probability of assignment)
- **Expected Premium**: $0.80-$1.20 per share
- **Collateral Required**: $2,800-2,900 per contract (100 shares)
- **Max Contracts with $2,487.77**: **0 contracts** ❌

**Problem**: Even SOFI requires $2,800+ in collateral per contract, which exceeds your buying power.

---

## Analysis: F - Ford (Only Viable Option)

**Current Price**: $13.46
**Stock Characteristics**: Stable dividend payer (4.39% yield), moderate volatility

### Cash-Secured Put Setup (30-45 DTE, 0.25 delta)
- **Strike Price**: $12.50 (approximately 7% OTM)
- **Delta**: ~0.25
- **Expected Premium**: $0.30-$0.45 per share (estimated)
- **Collateral Required**: $1,250 per contract
- **Max Contracts with $2,487.77**: **1 contract** ✓

### Income Calculation (F Stock)
```
Premium per share:        $0.35 (mid estimate)
Premium per contract:     $35.00 (100 shares)
Total contracts:          1
Total premium collected:  $35.00
DTE:                      37 days (mid-point)

Daily Income:             $35.00 / 37 = $0.95/day
Weekly Income:            $0.95 × 7 = $6.65/week
Annualized Return:        ($35 / $1,250) × (365/37) = 27.6%
Premium-to-Collateral:    2.8%
```

---

## Alternative Analysis: Splitting Capital Across Multiple F Contracts

Since Ford is the only stock you can afford with your buying power, you could:

**Option 1: Conservative (1 contract, $12.50 strike)**
- Collateral: $1,250
- Premium: ~$35
- Daily income: ~$0.95/day
- Remaining cash: $1,237 (idle)

**Option 2: Aggressive (2 contracts, different expirations)**
- Contract 1: $12.50 strike, 30 DTE, ~$30 premium
- Contract 2: $12.00 strike, 45 DTE, ~$40 premium
- Total collateral: $2,450
- Total premium: ~$70
- Daily income: ~$1.70/day (~$12/week)
- Remaining cash: $37

---

## Why Other Stocks Don't Work

### BAC ($53.57)
- Strike at 0.25 delta: ~$50
- Collateral needed: $5,000 per contract
- **You'd need $5,000 minimum** (201% more than you have)

### PLTR ($188.71)
- Strike at 0.25 delta: ~$175
- Collateral needed: $17,500 per contract
- **You'd need $17,500 minimum** (603% more than you have)

### AMD ($214.99)
- Strike at 0.25 delta: ~$200
- Collateral needed: $20,000 per contract
- **You'd need $20,000 minimum** (704% more than you have)

---

## FINAL RECOMMENDATION

### 🎯 With $2,487.77, Sell Puts on FORD (F):

**Best Setup**:
- **Stock**: F (Ford Motor Company)
- **Strategy**: Sell 1-2 cash-secured puts
- **Strike**: $12.50
- **Expiration**: 35-40 days out (aim for late January/early February 2026)
- **Expected Premium**: $30-40 per contract
- **Contracts**: 1 contract (conservative) or 2 contracts (aggressive)

**Income Projection**:
- **Premium Collected**: $35-70 total
- **Daily Income**: $0.95-1.90/day
- **Weekly Income**: $6.65-13.30/week
- **Annualized Return**: 27-30%

**Risk**:
If assigned, you'll buy 100-200 shares of Ford at $12.50/share.
- Effective cost basis: $12.15-12.20 (strike minus premium)
- Ford pays 4.39% dividend ($0.60/year), so you'd earn ~$60-120/year in dividends
- You'd own a quality dividend stock at a discount

---

## Reality Check: Meeting Your Income Goals

To generate meaningful daily income ($10/day = $300/month), you would need:

**Option 1**: Larger capital
- $10/day × 37 DTE = $370 premium needed
- At 3% premium rate → Need ~$12,300 buying power
- Could sell 10 Ford contracts or 4 SOFI contracts

**Option 2**: Higher risk strategies
- Credit spreads (less collateral required)
- Iron condors (collect premium both sides)
- 0-DTE or weekly options (higher premium, higher risk)

**Option 3**: Portfolio margin account
- 2-5x leverage on options
- Requires $25,000 minimum
- Much higher risk

---

## Summary Table

| Ticker | Current Price | Collateral/Contract | Max Contracts | Premium/Contract | Total Premium | Daily Income | Weekly Income |
|--------|---------------|---------------------|---------------|------------------|---------------|--------------|---------------|
| F      | $13.46        | $1,250              | 1-2           | $35              | $35-70        | $0.95-1.90   | $6.65-13.30   |
| SOFI   | $30-32        | $2,800-2,900        | 0             | $80-120          | $0            | $0           | $0            |
| BAC    | $53.57        | $5,000              | 0             | $100-150         | $0            | $0           | $0            |
| PLTR   | $188.71       | $17,500             | 0             | $350-500         | $0            | $0           | $0            |
| AMD    | $214.99       | $20,000             | 0             | $400-600         | $0            | $0           | $0            |

**Winner**: **Ford (F)** - Only stock you can trade with current buying power

---

## Sources
- [SOFI Stock Info - Yahoo Finance](https://finance.yahoo.com/quote/SOFI/)
- [Ford Stock Price - Yahoo Finance](https://finance.yahoo.com/quote/F/)
- [BAC Stock - Yahoo Finance](https://finance.yahoo.com/quote/BAC/)
- [Palantir Price Data - 24/7 Wall St](https://247wallst.com/forecasts/2025/12/29/palantir-technologies-pltr-price-prediction-and-forecast-2025-2030/)
- [AMD Stock Price - Investing.com](https://www.investing.com/equities/adv-micro-device)
- [Ford Options Analysis - Benzinga](https://www.benzinga.com/money/ford-stock-price-prediction)
- [Cash-Secured Puts Strategy - Phil Town Method](https://www.ruleoneinvesting.com/)

---

**Note**: These are estimates based on typical options premiums for stocks at these price levels. Actual premiums vary based on:
- Current implied volatility (IV)
- Exact expiration date
- Market conditions
- Bid-ask spread

To get exact premium quotes, check live options chains at:
- Yahoo Finance options chain
- Barchart.com
- ThinkorSwim
- Interactive Brokers
- Robinhood
