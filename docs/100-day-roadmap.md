# Realistic $100/Day Roadmap

**Created**: December 9, 2025
**Status**: Active R&D Phase (Day 9/90)
**Current P/L**: +$17.49 (from user hook)

## Executive Summary

This document provides a realistic, math-backed roadmap to achieving $100/day in trading profits. Based on our current infrastructure audit, **we have world-class plumbing but no profitable trading edge yet**.

### The Brutal Reality

| Metric | Current | Required | Gap |
|--------|---------|----------|-----|
| Sharpe Ratio | -45.86 (needs fix) | > 1.5 | Negative edge |
| Win Rate | 0% (7 trades) | > 60% | No data |
| Daily P/L | +$2.50/day avg | $100/day | $97.50/day |
| Statistical Trades | 7 | > 100 | 93 trades |

---

## Required Edge Math

### The Fundamental Equation

```
Daily Profit = Capital × Daily Return Rate × Win Contribution
```

To earn $100/day with different return profiles:

| Target Edge (Daily %) | Capital Required | Position Size @ 10% | Notes |
|-----------------------|------------------|---------------------|-------|
| 0.05% (conservative) | $200,000 | $20,000 | Need $200k deployed |
| 0.10% (moderate) | $100,000 | $10,000 | Current equity level |
| 0.20% (aggressive) | $50,000 | $5,000 | Requires 2x edge |
| 0.50% (options/theta) | $20,000 | $2,000 | Premium strategies |

**Key Insight**: At current $100k equity, we need a 0.10% daily edge (after fees) to hit $100/day.

### What 0.10% Daily Edge Looks Like

```
Scenario A: Win rate 55%, avg win 0.5%, avg loss -0.4%
  → Expected daily: (0.55 × 0.5%) + (0.45 × -0.4%) = 0.095% ≈ $95/day

Scenario B: Win rate 60%, avg win 0.4%, avg loss -0.3%
  → Expected daily: (0.60 × 0.4%) + (0.40 × -0.3%) = 0.12% ≈ $120/day

Scenario C: Win rate 65%, avg win 0.35%, avg loss -0.25%
  → Expected daily: (0.65 × 0.35%) + (0.35 × -0.25%) = 0.14% ≈ $140/day
```

---

## Phased Roadmap

### Phase 1: Fix Metrics & Validate Baseline (Days 9-30)
**Goal**: Establish trustworthy metrics and a working baseline

| Task | Owner | Status | Deadline |
|------|-------|--------|----------|
| Fix Sharpe calculation (volatility floor) | CTO | ✅ Done | Day 9 |
| Add minimum trade count to promotion gate | CTO | ✅ Done | Day 9 |
| Create ablation testing framework | CTO | ✅ Done | Day 9 |
| Run ablation tests on 4 key scenarios | CTO | Pending | Day 15 |
| Establish baseline Sharpe for momentum-only | CTO | Pending | Day 15 |
| Wire ProfitTargetTracker into daily loop | CTO | Pending | Day 20 |
| Reach 30+ trades for statistical significance | System | Pending | Day 30 |

**Success Criteria**:
- Sharpe ratio between -3 and +3 (reasonable bounds)
- Ablation report shows which gates add/subtract value
- Daily metrics automatically feed into budget recommendations

### Phase 2: Build Trading Edge (Days 31-60)
**Goal**: Achieve Sharpe > 1.0 through strategy refinement

| Task | Owner | Priority | Notes |
|------|-------|----------|-------|
| Ablation analysis: identify gate value | CTO | P0 | Which gates help? |
| Simplify to core momentum + risk | CTO | P0 | Remove complexity |
| Tune RL threshold based on ablation | CTO | P1 | May need lower threshold |
| Enable options (theta harvest) | CTO | P1 | Path to $10/day premium |
| Add trade-level attribution | CTO | P2 | PnL by gate |

**Success Criteria**:
- Sharpe > 1.0 across all 4 key scenarios
- Win rate > 55%
- Max drawdown < 15%
- 50+ trades with attribution data

### Phase 3: Validate Edge (Days 61-90)
**Goal**: Prove edge in out-of-sample period

| Task | Owner | Priority | Notes |
|------|-------|----------|-------|
| 30-day live paper validation | System | P0 | Real-time proof |
| Walk-forward validation | CTO | P0 | OOS performance |
| Options premium tracking | CTO | P1 | Real premium, not estimated |
| Scale test: $20/day → $50/day | CTO | P2 | Position size validation |

**Success Criteria**:
- Sharpe > 1.5 in live paper trading
- Win rate > 60%
- Max drawdown < 10%
- 100+ trades total

---

## Capital Scaling Schedule

Based on Fibonacci compounding strategy from CLAUDE.md:

| Phase | Daily Allocation | Cumulative Profit Required | Target Daily P/L |
|-------|------------------|---------------------------|------------------|
| Current | $10/day | $0 (baseline) | Break-even |
| Scale 1 | $20/day | $600 ($20 × 30 days) | $2-5/day |
| Scale 2 | $30/day | $900 ($30 × 30 days) | $5-10/day |
| Scale 3 | $50/day | $1,500 ($50 × 30 days) | $10-20/day |
| Scale 4 | $80/day | $2,400 ($80 × 30 days) | $20-40/day |
| Scale 5 | $130/day | $3,900 ($130 × 30 days) | $40-70/day |
| Scale 6 | $210/day | $6,300 ($210 × 30 days) | $70-100/day |

**Rule**: Only scale when cumulative profit ≥ next level × 30 days.

---

## Two Paths to $100/Day

### Path A: Pure Momentum/DCA (Slower, Lower Risk)

```
Requirements:
- Capital: $200,000+
- Daily Return: 0.05%
- Position Size: Full equity exposure
- Timeline: 12-18 months to scale

Pros: Lower complexity, more robust
Cons: Requires significant capital scale-up
```

### Path B: Momentum + Options Theta (Faster, Higher Complexity)

```
Requirements:
- Capital: $100,000 (current)
- Equity Return: 0.05% daily ($50/day)
- Options Premium: $50/day (theta harvest)
- Timeline: 6-9 months

Pros: Achievable with current capital
Cons: Options execution complexity
```

**Recommendation**: Pursue Path B with options enabled after Phase 2 validation.

---

## Options Contribution Plan

Current options infrastructure is scaffolded but disabled. Here's the activation plan:

### Theta Harvest Targets

| Strategy | Equity Gate | Est. Daily Premium | Capital Efficiency |
|----------|-------------|-------------------|-------------------|
| Cash-Secured Puts | $5,000 | $3-5/day | Low |
| Poor Man's Covered Calls | $5,000 | $5-8/day | Medium |
| Iron Condors | $10,000 | $8-15/day | High |
| Full Suite | $25,000 | $15-30/day | Highest |

### Options Activation Checklist

1. [ ] Set `ENABLE_THETA_AUTOMATION=true`
2. [ ] Re-enable `run_options_strategy()` in orchestrator
3. [ ] Wire ExecutionAgent for option orders
4. [ ] Validate with 5 dry-run trades
5. [ ] Track actual vs. estimated premium

---

## Risk Gates (Non-Negotiable)

These gates CANNOT be bypassed (Trade Gateway enforcement):

| Rule | Threshold | Rationale |
|------|-----------|-----------|
| Max Symbol Allocation | 15% | Concentration risk |
| Max Correlation | 80% | Diversification |
| Max Trades/Hour | 5 | Overtrading prevention |
| Min Trade Batch | $10 | Transaction cost efficiency |
| Max Daily Loss | 3% | Circuit breaker |
| Max Drawdown | 10% | Capital preservation |
| Max Risk Score | 0.75 | Aggregate risk limit |

---

## Monitoring & Checkpoints

### Weekly CEO Review (Every Friday)

```
Report Template:
- Week N of R&D Phase
- Trades executed: X
- Win rate: X%
- Sharpe (rolling 30d): X.XX
- P/L this week: $X.XX
- Cumulative P/L: $X.XX
- $100/day progress: X%
- Next week focus: [area]
```

### Milestone Gates

| Day | Checkpoint | Pass Criteria |
|-----|------------|---------------|
| 30 | Baseline established | 30+ trades, metrics trustworthy |
| 45 | Edge candidate | Sharpe > 0.5 in ablation |
| 60 | Edge validated | Sharpe > 1.0 multi-scenario |
| 75 | Scale test | Sharpe holds at $20/day |
| 90 | Promotion ready | All promotion gate criteria met |

---

## What NOT to Do

Based on the infrastructure assessment:

1. **Don't add more AI complexity** until baseline edge is proven
2. **Don't trust estimated options premium** - track real executions
3. **Don't scale capital** before statistical validation (100+ trades)
4. **Don't disable Trade Gateway** - it's the safety net
5. **Don't ignore ablation results** - cut gates that subtract value

---

## Appendix: Files to Monitor

| File | Purpose | Update Frequency |
|------|---------|------------------|
| `data/system_state.json` | Current state | Every trade |
| `data/ablation/ablation_results.csv` | Gate value analysis | After ablation runs |
| `reports/profit_target_report.json` | $100/day progress | Daily |
| `data/options_signals/*.json` | Options opportunities | Daily |
| `data/backtests/latest_summary.json` | Promotion gate input | After backtests |

---

## Summary

**Where we are**: World-class infrastructure, zero edge.

**What we need**:
1. Fix metrics (✅ Done)
2. Run ablation tests (Next)
3. Simplify strategy to what works
4. Validate with 100+ trades
5. Scale per Fibonacci schedule

**Timeline to $100/day**: 6-9 months (realistic)

**Path**: Momentum base ($50/day) + Options theta ($50/day) = $100/day

---

*This roadmap will be updated as we complete each phase and gather more data.*
