# R&D Phase Strategy (Days 1-90)

**Strategic Decision**: October 31, 2025 - CEO Approved

## Why R&D Phase?

**Brutal Truth Assessment**:
- Current P/L: -$0.14 (Day 3) - NOT profitable yet
- Current strategy: Simple buy-and-hold (NO trading edge)
- Reality: Building a Ferrari engine but driving in circles
- Need: 90 days to build profitable momentum + RL system

**Key Insight**:
We have **world-class infrastructure** (automation, agents, hygiene) but **no profitable trading edge yet**. R&D phase focuses on building that edge.

## R&D Phase Goals (90 Days)

### Month 1 (Days 1-30): Infrastructure + Data Collection
- ✅ Fibonacci strategy implemented
- ✅ Autonomous pre-commit hygiene
- ✅ Daily reporting automated
- 🔄 Collect 30 days of market data
- 🔄 Build momentum indicator system (MACD + RSI + Volume)
- **Target**: Break-even (small gains/losses acceptable)
- **Metric**: System reliability 99.9%+

### Month 2 (Days 31-60): Build Trading Edge
- 🎯 Implement MACD + RSI + Volume entry/exit system
- 🎯 Add stop-losses and profit-taking rules
- 🎯 Build RL agent (Research, Signal, Risk, Execution subagents)
- 🎯 Backtest with 60 days of collected data
- **Target**: Win rate >55%, Sharpe ratio >1.0
- **Metric**: Consistent small profits ($0.50-2/day)

### Month 3 (Days 61-90): Validate & Optimize
- 🎯 30 days of live testing with momentum + RL system
- 🎯 Tune parameters based on real performance
- 🎯 Add Alpha Vantage news sentiment
- 🎯 Implement dynamic position sizing
- **Target**: Win rate >60%, Sharpe ratio >1.5
- **Metric**: Consistent profits ($3-5/day)

## Success Criteria (Day 90)

All metrics are now tied to Anthropic’s [Define Success](define-success.md) scorecard so our R&D checkpoints align with enterprise evaluation best practices.

**Go/No-Go for Scaling**:
```python
if (
    win_rate > 60 and
    sharpe_ratio > 1.5 and
    max_drawdown < 10 and
    profitable_30_days and
    no_critical_bugs
):
    # APPROVED: Scale to live trading with Fibonacci
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

### DON'T Worry About:
- ❌ Daily P/L of $0.03 or -$0.14 (noise)
- ❌ Being profitable every single day
- ❌ Scaling Fibonacci yet (wait until profitable)
- ❌ Going live with real money (paper trading until Month 4+)

### Mindset Shift:
- **Old**: "We need to make money TODAY"
- **New**: "We're building a system that makes $100+/day by Month 6"

## R&D Phase Investments

**Current Approach** (October 31 - approved):
- Invest ~$3-10/day via Fibonacci for testing
- Focus: Collect data, test strategies, validate automation
- Expectation: Break-even to small losses acceptable
- Total R&D "cost": ~$270 over 90 days (acceptable tuition fee)

**If profitable during R&D**: BONUS! Banking profits for future scaling.
**If break-even during R&D**: EXPECTED! System learning, data collecting.
**If small losses during R&D**: ACCEPTABLE! Building edge worth the tuition.

---

## Current Challenge Status (Updated Live)

**90-Day R&D Challenge**: Day 2 of 90 (2% complete) - PAPER TRADING
**Start Date**: October 29, 2025
**Current Phase**: Month 1 - Infrastructure + Data Collection
**Current P/L**: +$0.02 (PROFITABLE - beating expectations!)
**System Status**: ✅ Infrastructure solid, building trading edge

### Current Positions:
- SPY (Core ETF): +$0.03 profit (+0.18%) ✅
- NVDA (Growth): +$0.01 profit (+0.48%) ✅
- GOOGL (Growth): -$0.02 loss (-1.16%) ❌

### Key Learnings (Compounding):
- Day 1: System automation validated - SPY $6, GOOGL $2 (total $8 invested)
- Day 2: Continued execution - SPY $6, NVDA $2 (total $8 invested)
- Win Rate: 50% (2 winning trades, 1 losing trade, 1 neutral)
- Pattern: Need momentum indicators - adding MACD + Volume confirmation
- Next: Implement MACD + Volume system (Today - CTO executing)

### Timeline:
**Next Execution**: Day 3 trades at 9:35 AM ET (October 31, 2025)
**Next Milestone**: Day 30 - Month 1 R&D review
