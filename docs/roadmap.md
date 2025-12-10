# Trading System Roadmap

> **North Star Goal**: $100/day net profit
>
> This roadmap prioritizes work by expected P&L impact, not just technical merit.

## Current Status

| Metric | Current | Target | Gap |
|--------|---------|--------|-----|
| Average Daily P&L | ~$5 | $100 | $95 |
| Win Rate | 52% | 60%+ | 8% |
| Sharpe Ratio | 0.8 | 1.5+ | 0.7 |
| Capital | $10,000 | $20,000+ | $10,000 |

---

## Priority Framework

All work is prioritized by **expected P&L impact**:

```
Impact = (Probability of Success) × (Expected Daily P&L Improvement) × (Time to Complete⁻¹)
```

### Priority Levels

| Priority | Expected Impact | Timeframe |
|----------|-----------------|-----------|
| P0 | > $20/day improvement | This week |
| P1 | $10-20/day improvement | Next 2 weeks |
| P2 | $5-10/day improvement | This month |
| P3 | < $5/day improvement | Next quarter |

---

## Next 3 Branches (Highest P&L Impact)

### 1. Position Sizing Optimization (P0)

**Branch**: `feat/kelly-position-sizing`

**Problem**: Current fixed position sizing leaves money on the table during high-confidence signals.

**Expected Impact**: +$15-25/day

**Changes**:
- [ ] Implement Kelly criterion with volatility scaling
- [ ] Add confidence-weighted sizing from RL model
- [ ] Cap maximum position at 15% of portfolio
- [ ] Add regime-based sizing (reduce in volatile markets)

**Metrics to Track**:
- Average position size increase
- Risk-adjusted return improvement
- Maximum drawdown change

**Completion Criteria**:
- Backtest shows +$15/day improvement
- Max drawdown unchanged or improved
- 2 weeks paper trading validation

---

### 2. Exit Logic Enhancement (P0)

**Branch**: `feat/dynamic-exits`

**Problem**: Current exits are too rigid. Missing profit on winners, taking too much loss on losers.

**Expected Impact**: +$10-15/day

**Changes**:
- [ ] Add trailing stop based on ATR
- [ ] Implement time-based profit targets
- [ ] Add sentiment-triggered early exits
- [ ] Volatility-adjusted stop losses

**Metrics to Track**:
- Average winner size
- Average loser size
- Win/loss ratio
- Holding period optimization

**Completion Criteria**:
- Backtest shows improved win/loss ratio
- Average winner increases by 20%
- Average loser decreases by 15%

---

### 3. Entry Signal Filtering (P1)

**Branch**: `feat/signal-filters`

**Problem**: Taking too many marginal trades that dilute returns.

**Expected Impact**: +$8-12/day

**Changes**:
- [ ] Add volume confirmation filter
- [ ] Implement multi-timeframe confirmation
- [ ] Add market regime filter (avoid choppy markets)
- [ ] Integrate sentiment threshold gates

**Metrics to Track**:
- Trade frequency reduction
- Win rate improvement
- Quality score of trades taken

**Completion Criteria**:
- Trade count reduced by 30%
- Win rate increased by 5%
- Net P&L maintained or improved

---

## Backlog (Ordered by P&L Impact)

### P1: Near-Term (Next 2 Weeks)

| Item | Expected Impact | Effort |
|------|-----------------|--------|
| Options premium strategy activation | +$10-15/day | Medium |
| Sector rotation overlay | +$8-12/day | Medium |
| Intraday momentum capture | +$5-10/day | High |

### P2: Medium-Term (This Month)

| Item | Expected Impact | Effort |
|------|-----------------|--------|
| RL model continuous training | +$5-8/day | High |
| Multi-asset portfolio allocation | +$5-10/day | High |
| Weekend crypto trading | +$3-5/day | Low |

### P3: Long-Term (Next Quarter)

| Item | Expected Impact | Effort |
|------|-----------------|--------|
| Market making strategy | +$10-20/day | Very High |
| Alternative data integration | +$5-10/day | High |
| Full automation with no manual review | +$2-3/day | Medium |

---

## Iteration Cadence

### Daily
- [ ] Check overnight P&L
- [ ] Review open positions
- [ ] Note any system issues

### Weekly (Friday)
- [ ] Update this roadmap with actual vs. expected impact
- [ ] Regenerate core backtest with latest changes
- [ ] Review branch/PR status
- [ ] Decide: Continue current branches or pivot?

### Monthly (Last Friday)
- [ ] Full strategy review
- [ ] Update capital requirements model
- [ ] Evaluate $100/day progress
- [ ] Set next month's priorities

### After Each Merged PR
1. Run full backtest suite
2. Compare metrics to baseline:
   - Did average daily P&L improve?
   - Did Sharpe ratio improve?
   - Did max drawdown stay acceptable?
3. Update progress tracker
4. Update this roadmap

---

## Metrics Dashboard

Run this to see current progress:

```bash
python scripts/generate_progress_dashboard.py
```

Key outputs:
- Progress toward $100/day (%)
- Days above target this month
- Trend direction (improving/declining)
- Expected time to target

---

## Branch/PR Tracking

### Open Branches
| Branch | Focus | Status | Expected Impact |
|--------|-------|--------|-----------------|
| cursor/100-day-target-infrastructure | Target model, registry | In Progress | +$0 (infra) |

### Recently Merged
| PR | Focus | Actual Impact | Notes |
|----|-------|---------------|-------|
| #111 | CI fixes | $0 | Maintenance |
| #110 | Research infrastructure | $0 | Foundation |

### Upcoming
| Planned Branch | Focus | Expected Impact |
|----------------|-------|-----------------|
| feat/kelly-position-sizing | Position sizing | +$15-25/day |
| feat/dynamic-exits | Exit logic | +$10-15/day |
| feat/signal-filters | Entry filtering | +$8-12/day |

---

## Decision Log

| Date | Decision | Rationale | Outcome |
|------|----------|-----------|---------|
| 2025-12-03 | Created $100/day target model | Make goal explicit | Pending |
| 2025-12-03 | Created strategy registry | Avoid duplicate work | Pending |

---

## Risk Assessment

### What Could Derail $100/Day Goal

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Market regime change | Medium | High | Regime detection, hedging |
| Strategy overfitting | Low | High | Walk-forward validation |
| Capital constraints | Medium | Medium | Compound strategy |
| Execution issues | Low | Medium | Broker health monitoring |
| API outages | Low | Medium | Fallback procedures |

---

## Success Criteria for $100/Day

To declare victory on the $100/day goal, we need:

1. ✅ 30 consecutive trading days averaging $100+/day
2. ✅ Maximum drawdown < 10% of capital
3. ✅ Sharpe ratio > 1.5
4. ✅ Win rate > 55%
5. ✅ No P1 incidents during the period
6. ✅ System running autonomously (no manual intervention)

---

**Last Updated**: 2025-12-03
**Next Review**: 2025-12-06 (Friday)
**Owner**: Trading System (CTO: Claude)
