# R&D Phase Strategy (Days 1-90)

**Strategic Decision**: October 31, 2025 - CEO Approved

## Why R&D Phase?

**Key Insight**:
We have **world-class infrastructure** (automation, agents, hygiene) but building profitable trading edge. R&D phase focuses on validating that edge with paper trading before scaling.

## R&D Phase Goals (90 Days)

### Month 1 (Days 1-30): Infrastructure + Data Collection
- ✅ Fibonacci strategy implemented
- ✅ Autonomous pre-commit hygiene
- ✅ Daily reporting automated
- ✅ 30+ days of market data collected
- ✅ Momentum indicator system (MACD + RSI + Volume)
- **Result**: System reliability 99.9%+

### Month 2 (Days 31-60): Build Trading Edge
- ✅ MACD + RSI + Volume entry/exit system
- ✅ Stop-losses and profit-taking rules
- ✅ RL agent (Research, Signal, Risk, Execution subagents)
- ✅ Thompson Sampling strategy selection
- ✅ Trade memory with SQLite journal
- **Result**: Win rate 80%, system validated

### Month 3 (Days 61-90): Validate & Optimize - CURRENT
- 🔄 Live testing with real deposits ($10/day)
- 🔄 Accumulating capital for options spreads
- 🔄 Phil Town Rule #1 strategy integration
- 🎯 Target: $200 capital for first CSP
- **Target**: Win rate >60%, Sharpe ratio >1.5

## Success Criteria (Day 90)

All metrics align with enterprise evaluation best practices for R&D trading systems.

**Go/No-Go for Scaling**:
```python
if (
    win_rate > 60 and
    sharpe_ratio > 1.5 and
    max_drawdown < 10 and
    profitable_30_days and
    no_critical_bugs
):
    # APPROVED: Scale to live trading
    scale_to_live = True
else:
    # EXTEND R&D: Need more time
    extend_rd_phase()
```

### Enforcement Automation

- `scripts/run_backtest_matrix.py` runs the regime matrix in `config/backtest_scenarios.yaml` and persists structured metrics under `data/backtests/`.
- `scripts/enforce_promotion_gate.py` consumes `data/system_state.json` plus the latest matrix summary and exits non-zero if any criterion above fails.
- `.github/workflows/daily-trading.yml` runs both steps before the orchestrator so live trading cannot start unless the guard returns green.

## What "R&D Phase" Means

### DO Focus On:
- ✅ Building profitable trading edge
- ✅ System reliability and automation
- ✅ Data collection and learning
- ✅ Agent intelligence and introspection
- ✅ Infrastructure improvements
- ✅ Capital accumulation for options spreads

### DON'T Worry About:
- ❌ Small daily P/L (noise at current capital levels)
- ❌ Being profitable every single day
- ❌ Scaling yet (wait until $200+ capital)
- ❌ Complex strategies (stick to Phil Town Rule #1)

### Mindset Shift:
- **Old**: "We need to make money TODAY"
- **New**: "We're building a system that makes $100+/day by Month 6"

## Capital Accumulation Strategy

**Current Approach** (January 2026):
- Deposit $10/day via Alpaca
- Accumulate until $200 for first CSP
- Target first trade: ~Jan 29, 2026
- Reinvest ALL profits (compounding)

**Capital Tiers**:
| Capital | Daily Target | Strategy |
|---------|--------------|----------|
| $200 | $5/day | Single CSP on SPY |
| $500 | $15/day | 2 CSPs or Iron Condor |
| $1,000 | $30/day | Wheel on SPY |
| $2,000 | $60/day | Multiple wheels |
| $5,000 | **$100/day** | Full Phil Town |

---

## Current Challenge Status

**90-Day R&D Challenge**: Day 70 of 90 (78% complete) - Jan 7, 2026
**Current Phase**: Month 3 - Validate & Optimize
**Live Account**: $30 (accumulating $10/day)
**System Status**: ✅ Infrastructure solid, accumulating capital

### Key Milestones:
- Day 1 (Oct 29, 2025): System automation validated
- Day 30: Month 1 complete - infrastructure solid
- Day 60: Month 2 complete - trading edge validated
- Day 69 (Jan 6, 2026): Fresh start with $10/day deposits
- Day 70 (Jan 7, 2026): Phil Town CSPs executed (+$16,661 paper P/L!)
- Day 90 (Jan 27, 2026): R&D phase complete - Go/No-Go decision

### Timeline:
**Next Milestone**: Day 90 - R&D Phase Complete
**Target for First Trade**: ~$200 capital (~Jan 29, 2026)
