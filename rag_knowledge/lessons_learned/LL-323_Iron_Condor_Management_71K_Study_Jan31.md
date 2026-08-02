# LL-323: Iron Condor Management - 71,417 Trade Study

**Date**: January 31, 2026
**Category**: Research / Position Management
**Severity**: HIGH
**Related**: LL-268, LL-277, LL-299, LL-321

## Summary

Analysis of 71,417 iron condor trades on SPY (2007-2017) reveals optimal management strategies.

## Study Parameters

| Parameter    | Value                                          |
| ------------ | ---------------------------------------------- |
| Underlying   | SPY                                            |
| Period       | Jan 2007 - Mar 2017                            |
| Total trades | 71,417                                         |
| Setup 1      | 16-delta short / 5-delta long (40,868 trades)  |
| Setup 2      | 30-delta short / 16-delta long (30,549 trades) |

## Key Findings

### 1. Optimal Profit-Taking by Delta

| Delta Setup         | Optimal Profit Target | Rationale                                   |
| ------------------- | --------------------- | ------------------------------------------- |
| **16-delta (wide)** | **50-75%**            | Higher win rate, more efficient capital use |
| 30-delta (tight)    | 25-50%                | Faster profit capture needed                |

### 2. Win Rate by Profit Target

| Profit Target | Win Rate | Avg Days Held |
| ------------- | -------- | ------------- |
| 25%           | ~92%     | ~8 days       |
| 50%           | ~85%     | ~14 days      |
| 75%           | ~75%     | ~25 days      |
| Expiration    | ~68%     | ~45 days      |

**Key insight**: Closing at 50% captures most profit in ~40% of the time.

### 3. Commission-Adjusted Performance

When accounting for $1/contract commissions:

- **16-delta condors**: 50-75% profit targets optimal
- **30-delta condors**: 25-50% profit targets optimal

### 4. VIX Impact on Returns

| VIX Level       | 30-Delta Performance            |
| --------------- | ------------------------------- |
| Low (< 15)      | Below average                   |
| Medium (15-20)  | Average                         |
| **High (> 20)** | **Significantly above average** |

**Trading 30-delta iron condors during high VIX environments substantially outperformed** other volatility regimes.

## Practical Application for Our Strategy

### Our Setup

- **Delta**: 15-20 (between study's 16 and 30)
- **Wings**: $5 wide
- **DTE**: 30-45 days

### Recommended Management (Based on Study)

| Condition                | Action                        |
| ------------------------ | ----------------------------- |
| Hit 50% profit           | **CLOSE**                     |
| 7 DTE reached            | **CLOSE** (regardless of P/L) |
| 200% loss                | **CLOSE** (stop-loss)         |
| Tested side at 25+ delta | Consider adjustment           |

### Expected Performance (Based on Study)

| Metric                   | 16-Delta Condors | Our 15-20 Delta |
| ------------------------ | ---------------- | --------------- |
| Win rate (50% target)    | ~85%             | ~86% expected   |
| Avg profit (per $5 wide) | ~$75-100         | ~$75-100        |
| Avg loss (per trade)     | ~$200-250        | ~$200-250       |
| Profit factor            | ~1.5             | ~1.5 expected   |

## Risk-Reward Math

**Why 50% profit target matters:**

Traditional iron condor risk:reward ≈ 3:1 (risk $300 to make $100)

If letting trades expire:

- Need 75%+ win rate just to break even
- One loss = 3-4 winners needed to recover

With 50% profit target:

- Risk:reward improves to ~1.5:1
- Faster capital turnover
- More forgiving of occasional losses

## The 50% / 50% Rule

Study supports using:

- **50% profit target** (take profits)
- **50% stop-loss** (or 200% of credit)

This transforms the asymmetric risk into a more balanced trade.

## Capital Efficiency

| Strategy              | Trades/Month | Capital Turns/Year |
| --------------------- | ------------ | ------------------ |
| Hold to expiration    | 1            | 12                 |
| **50% profit target** | **2-3**      | **24-36**          |

More frequent trades = more opportunities to compound.

## Implementation Checklist

1. [ ] Set 50% profit alert when entering trade
2. [ ] Set 7 DTE reminder (mandatory close)
3. [ ] Set 200% loss stop-loss
4. [ ] Track actual vs expected win rate
5. [ ] Review after 30 trades for adjustment

## Sources

- [Project Finance - Iron Condor Management Study (71,417 trades)](https://www.projectfinance.com/iron-condor-management/)
- [arXiv - Stochastic Optimal Control of Iron Condor Portfolios](https://arxiv.org/html/2501.12397v1)
- [Apex Vol - Iron Condor Strategy 2026](https://apexvol.com/strategies/iron-condor)
- [Trasignal - 10 Steps to Master Iron Condors 2026](https://trasignal.com/blog/learn/iron-condor-strategy/)
- [QuantStrategy - Build and Adjust Iron Condor Strategy](https://quantstrategy.io/blog/how-to-build-and-adjust-the-iron-condor-strategy-for/)

## Tags

`iron-condor`, `management`, `research`, `50-percent-profit`, `win-rate`, `capital-efficiency`
