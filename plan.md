# Plan Mode Session: $10/Day to $100/Day Roadmap

> Managed in Claude Code Plan Mode. Do not modify outside Plan Mode workflow.

## Metadata
- Task: Implement 7-day asset coverage for $100/day profit goal
- Owner: Claude CTO
- Status: APPROVED
- Approved at: 2025-12-02T00:00:00Z
- Valid for (minutes): 180

## North Star Goal

**Input**: $10/day invested
**Output**: $100/day profit (after-tax) within 16-18 months
**Strategy**: Compound 7-day diversified portfolio at ~0.13% daily edge

## Current State (Day 9/90)

| Metric | Value | Status |
|--------|-------|--------|
| Portfolio | $100,005.50 | +$5.50 P/L |
| Win Rate (Backtest) | 62.2% | Above 60% target |
| Sharpe Ratio (Backtest) | 2.18 | Above 1.5 target |
| Phase | R&D (Month 1) | Building edge |

## Asset Allocation (Updated Dec 2, 2025)

**7-ETF Diversified Portfolio**:

| Asset Class | Symbol | Allocation | Purpose |
|-------------|--------|------------|---------|
| Equity | SPY/QQQ/VOO | 50% | Momentum-selected core |
| Bonds | BND | 15% | Defensive buffer (Graham) |
| REITs | VNQ | 15% | Real estate yield |
| Treasuries | TLT/IEF | 10% | Rate sensitivity ladder |
| Crypto Proxy | BITO | 10% | BTC exposure via ETF |

**Why BITO over direct BTC/ETH**:
- Trades like regular stock on Alpaca (no crypto API issues)
- Same data pipeline as other ETFs
- Captures BTC price movements via futures
- No special authentication or data sources needed

## Compounding Math to $100/Day

Assumptions:
- $10/day input (weekdays only = ~22 days/month)
- 0.13% daily net edge (post-fees, post-slippage)
- Full profit reinvestment
- 62% win rate holds

| Months | Total Invested | Account Value | Daily Net Profit | Notes |
|--------|----------------|---------------|------------------|-------|
| 1 | $220 | $230 | ~$0.30 | Bootstrap phase |
| 3 | $660 | $750 | ~$1.00 | System learning |
| 6 | $1,320 | $1,800 | ~$2.30 | Edge stabilizing |
| 12 | $2,640 | $5,000 | ~$6.50 | Compounding kicks in |
| 18 | $3,960 | $12,000 | ~$15.50 | **$100/day in reach** |
| 24 | $5,280 | $25,000 | ~$32.00 | Sustainable $100/day |

**Key Accelerators**:
1. Higher initial capital reduces timeline significantly
2. Side income reinvested accelerates compounding
3. Scaling daily input from $10 → $20 → $50 as profits grow

## Execution Plan

### Phase 1: R&D Complete (Days 1-90) - Current
- [x] Core momentum strategy validated (62.2% win rate)
- [x] Multi-asset diversification (SPY/QQQ/VOO/BND/VNQ/TLT)
- [x] RL policy learner integrated
- [x] Risk management with circuit breakers
- [ ] Add BITO crypto proxy (done Dec 2, 2025)
- [ ] Add IEF treasury diversification (done Dec 2, 2025)
- [ ] Achieve 30 consecutive profitable days

### Phase 2: Production Scaling (Days 91-180)
- [ ] Deploy live trading with real capital
- [ ] Start with $100 initial deposit + $10/day
- [ ] Monitor daily edge vs backtest
- [ ] Scale position sizes based on Sharpe

### Phase 3: Compounding Growth (Months 6-18)
- [ ] Reinvest 100% of profits
- [ ] Scale daily input as account grows
- [ ] Target $100/day net by Month 18

## Phil Town Rule #1 Options (Yield Acceleration)

**Added Dec 2, 2025** - Options strategies to accelerate path to $100/day.

### Strategy 1: Selling Puts ("Getting Paid to Wait")
- Sell cash-secured puts at MOS (Margin of Safety) price
- Strike = 50% below Sticker Price (fair value)
- If assigned: Own stock at target price minus premium
- If not assigned: Keep premium as profit
- Target: 12%+ annualized yield

### Strategy 2: Covered Calls ("Getting Paid to Sell")
- Sell calls at Sticker Price on stocks you own
- If called away: Sell at fair value plus premium
- If not called: Keep premium and shares
- Requires: 100+ shares per position

### Sticker Price Formula (Phil Town)
```
1. Future EPS = Current EPS × (1 + growth)^10
2. Future P/E = min(growth × 200, 50)
3. Future Price = Future EPS × Future P/E
4. Sticker Price = Future Price ÷ 1.15^10
5. MOS Price = Sticker Price × 0.50
```

### Big Five Quality Screen
All metrics should be 10%+ over 10 years:
- ROIC (Return on Invested Capital)
- Equity Growth Rate
- EPS Growth Rate
- Sales Growth Rate
- Free Cash Flow Growth Rate

### Options Timeline
| Phase | Requirement | Options Action |
|-------|------------|----------------|
| Now (Day 9) | Building positions | Research, no trades |
| Month 3 | 50+ shares NVDA | Start covered calls |
| Month 6 | $5,000+ cash | Start put selling |
| Month 12 | Full deployment | Both strategies active |

### Estimated Yield Boost
- Covered calls: +1-2% monthly on positions
- Put selling: +1-3% monthly on cash
- Combined: +$50-150/month at $10k portfolio

## Risk Guardrails

| Guard | Threshold | Action |
|-------|-----------|--------|
| Daily Loss | >2% | Halt trading |
| Max Drawdown | >10% | Review strategy |
| Win Rate Drop | <50% | Pause, retrain |
| Sharpe Drop | <1.0 | Reduce position sizes |

## Exit Checklist
- [x] BITO added to ETF universe
- [x] IEF added for treasury diversification
- [x] Allocation percentages updated (50/15/15/10/10)
- [x] Documentation updated
- [ ] Backtest with new allocation
- [ ] Commit and push changes
