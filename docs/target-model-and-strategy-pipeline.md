# Target Model & Strategy Pipeline Documentation

**Created:** 2025-12-03
**Purpose:** Make $100/day North Star an explicit, measurable design constraint

## Overview

This document describes the new infrastructure that transforms the $100/day goal from a narrative aspiration into an encoded constraint with measurable progress tracking.

---

## Components

### 1. Target Model (`src/analytics/target_model.py`)

**What it does:**
- Calculates capital, risk, and performance requirements to achieve $100/day target
- Provides feasibility assessment (is this realistic with given capital?)
- Tracks progress toward target with real performance data
- Outputs metrics like required Sharpe ratio, win rate, daily return %

**Key Insight:**
> The target model reveals that $100/day with $100k capital requires **10+ trades/day**, which triggers PDT restrictions. This makes it clear we need either:
> - More capital ($250k+ for comfortable day trading)
> - Longer hold periods (swing trading instead of day trading)
> - Lower daily target initially ($30-50/day is more realistic with $100k)

**Usage:**
```bash
# View requirements for $100/day with $100k capital
python3 scripts/generate_target_model_report.py

# View requirements for different capital amounts
python3 scripts/generate_target_model_report.py --capital 250000

# Track progress (includes actual backtest performance)
python3 scripts/generate_target_model_report.py
```

**Output Example:**
```
REQUIREMENTS TO HIT TARGET:
  • Daily Return: 0.103%
  • Annual Return: 29.6%
  • Sharpe Ratio: 1.50+
  • Win Rate: 60%+
  • Trades/Day: 10.3
  • Max Drawdown: <10.0%

FEASIBILITY: 80/100
  • Status: ❌ NOT FEASIBLE
  • Skill Required: Intermediate (Top 20% of traders)
  • Risk Level: HIGH - Not recommended without significant improvements

⚠️  WARNINGS:
  • Required 10.3 trades/day is high (>10) - may trigger PDT
```

---

### 2. Strategy Registry (`src/strategies/strategy_registry.py`)

**What it does:**
- Single source of truth for all trading strategies
- Tracks strategy status: concept → development → backtested → paper → live
- Links strategies to branches/PRs to prevent duplicate work
- Stores backtest metrics for performance comparison
- Enables rational decisions: "Should I improve existing strategy or add new one?"

**Strategy Lifecycle:**
1. **Concept** - Initial idea, not implemented
2. **Development** - Being developed in a branch
3. **Backtested** - Has backtest results
4. **Paper Trading** - Currently paper trading
5. **Live** - Deployed to live trading
6. **Deprecated** - No longer in use
7. **Failed** - Tried and didn't work

**Usage:**
```bash
# View all strategies
PYTHONPATH=src python3 src/strategies/strategy_registry.py report

# List strategies by status
PYTHONPATH=src python3 src/strategies/strategy_registry.py list

# Find best performing strategy
PYTHONPATH=src python3 src/strategies/strategy_registry.py best sharpe_ratio
```

**Registering a New Strategy:**
```python
from src.strategies.strategy_registry import (
    StrategyRegistry, StrategyRecord, StrategyType, StrategyStatus
)

registry = StrategyRegistry()

strategy = StrategyRecord(
    strategy_id="my_new_strategy_v1",
    name="My New Strategy",
    description="Description of what it does",
    strategy_type=StrategyType.MOMENTUM,
    module_path="src.strategies.my_strategy",
    class_name="MyStrategy",
    status=StrategyStatus.DEVELOPMENT,
    branch="feature/my-new-strategy",
)

registry.register(strategy)
```

---

### 3. Branch & Strategy Analysis Dashboard (`scripts/analyze_branches_and_strategies.py`)

**What it does:**
- Shows all active branches and what they're working on
- Lists open PRs with status
- Displays strategy registry status
- Identifies potential conflicts (multiple branches editing same files)
- Provides recommendations (e.g., "finish backtested strategies before starting new ones")

**Usage:**
```bash
# Generate full dashboard
python3 scripts/analyze_branches_and_strategies.py

# Save to file
python3 scripts/analyze_branches_and_strategies.py > reports/branch_analysis.txt
```

**Output Includes:**
- Active branches and their commits
- Open PRs with metadata
- Strategy registry status by lifecycle stage
- Branch activity analysis (which files each branch touches)
- Potential conflicts and duplicate work warnings
- Top performing strategies
- Recommendations for next steps

---

### 4. Backtest Metrics Updater (`scripts/update_backtest_metrics.py`)

**What it does:**
- Reads backtest results and updates strategy registry
- Enables tracking of which strategies perform best
- Automates the process of keeping registry in sync with backtest data

**Usage:**
```bash
# Update specific strategy
python3 scripts/update_backtest_metrics.py \
  --strategy-id momentum_v1 \
  --backtest-file data/backtests/momentum_v1_backtest.json

# Scan and update all backtests
python3 scripts/update_backtest_metrics.py --scan-all
```

---

## Integration into Daily Workflow

### Morning Routine (9:00 AM EST)
```bash
# 1. Check target model progress
python3 scripts/generate_target_model_report.py

# 2. Review strategy status
PYTHONPATH=src python3 src/strategies/strategy_registry.py report

# 3. Check for conflicts/duplicate work
python3 scripts/analyze_branches_and_strategies.py
```

### After Backtest
```bash
# Update strategy registry with new metrics
python3 scripts/update_backtest_metrics.py --scan-all

# Check if we're closer to $100/day target
python3 scripts/generate_target_model_report.py
```

### Before Starting New Work
```bash
# Check what's already in progress
python3 scripts/analyze_branches_and_strategies.py

# Check strategy registry to avoid duplication
PYTHONPATH=src python3 src/strategies/strategy_registry.py list
```

---

## Key Insights from Target Model

### Capital Requirements for $100/Day

| Capital   | Daily Return | Trades/Day | PDT Risk | Feasibility |
|-----------|--------------|------------|----------|-------------|
| $10,000   | 1.03%        | 100+       | ❌ HIGH  | Not feasible |
| $25,000   | 0.41%        | 40+        | ⚠️ HIGH  | Difficult |
| $100,000  | 0.10%        | 10+        | ⚠️ MEDIUM| Challenging |
| $250,000  | 0.04%        | 4-5        | ✅ LOW   | Achievable |

**Conclusion:** With current $100k paper trading account, $100/day target requires very high frequency trading (10+ trades/day), which:
1. Risks triggering PDT restrictions
2. Increases slippage costs
3. Requires advanced execution quality
4. Demands high Sharpe ratio (1.5+) to be sustainable

**Recommendations:**
1. **Short term:** Target $30-50/day with $100k (3-5 trades/day, more realistic)
2. **Medium term:** Compound profits to increase capital
3. **Long term:** Once capital reaches $250k+, increase target to $100/day

---

## Canonical Strategy Pipeline

To avoid duplicate work and ensure systematic progress:

1. **All strategies must be registered** in the strategy registry
2. **Before developing new strategy:**
   - Check registry for similar strategies
   - Check open branches/PRs for ongoing work
   - Document why new strategy is needed vs improving existing
3. **Development flow:**
   - Register strategy with status=DEVELOPMENT
   - Link to branch/PR
   - Run backtests and update metrics
   - Progress through lifecycle: development → backtested → paper → live
4. **Metrics-driven decisions:**
   - Compare strategies using registry metrics
   - Choose best performer for deployment
   - Archive or deprecate underperforming strategies

---

## Integration with CI/CD

### Automated Checks (Future Enhancement)
```yaml
# .github/workflows/backtest-and-check-target.yml
- name: Run backtests
  run: python3 scripts/run_backtest_matrix.py

- name: Update strategy registry
  run: python3 scripts/update_backtest_metrics.py --scan-all

- name: Check progress to $100/day target
  run: python3 scripts/generate_target_model_report.py

- name: Analyze branches for conflicts
  run: python3 scripts/analyze_branches_and_strategies.py
```

---

## Files Created

```
src/
  analytics/
    target_model.py                     # $100/day constraint encoding
  strategies/
    strategy_registry.py                # Strategy lifecycle management

scripts/
  generate_target_model_report.py      # CLI for target model reports
  update_backtest_metrics.py           # Update registry with backtest data
  analyze_branches_and_strategies.py   # Dashboard for branches/PRs/strategies

docs/
  ops/
    RUNBOOK.md                          # Operations runbook
  target-model-and-strategy-pipeline.md # This file

data/
  strategy_registry.json                # Strategy registry database (auto-created)
```

---

## Example Workflow: Adding a New Strategy

```bash
# 1. Check what exists
python3 scripts/analyze_branches_and_strategies.py
PYTHONPATH=src python3 src/strategies/strategy_registry.py list

# 2. Create branch
git checkout -b feature/mean-reversion-v1

# 3. Register strategy
python3 -c "
from src.strategies.strategy_registry import *
registry = StrategyRegistry()
strategy = StrategyRecord(
    strategy_id='mean_reversion_v1',
    name='Mean Reversion Strategy V1',
    description='RSI-based mean reversion on SPY',
    strategy_type=StrategyType.MEAN_REVERSION,
    module_path='src.strategies.mean_reversion',
    class_name='MeanReversionStrategy',
    status=StrategyStatus.DEVELOPMENT,
    branch='feature/mean-reversion-v1',
)
registry.register(strategy)
"

# 4. Implement strategy
# ... write code ...

# 5. Run backtest
python3 scripts/run_backtest_matrix.py

# 6. Update registry with results
python3 scripts/update_backtest_metrics.py --scan-all

# 7. Check progress to target
python3 scripts/generate_target_model_report.py

# 8. Create PR
gh pr create --title "feat: Mean reversion strategy" --body "..."

# 9. After merge, update status
python3 -c "
from src.strategies.strategy_registry import *
registry = StrategyRegistry()
registry.update_status('mean_reversion_v1', StrategyStatus.BACKTESTED)
"
```

---

## Next Steps

1. **Productize Core Strategy:**
   - Freeze momentum strategy rules
   - Create reference backtest (1-2 years CSV)
   - Add CI check that fails if metrics degrade

2. **Add Daily Reporting:**
   - Integrate target model progress into daily reports
   - Track "days at $100+" metric
   - Show gap analysis daily

3. **Portfolio Optimization:**
   - Once multiple strategies validated, add portfolio allocator
   - Risk-weight strategies based on Sharpe/correlation
   - Dynamic position sizing based on target model

4. **Continuous Improvement Loop:**
   - Weekly: Review strategy registry and target progress
   - Monthly: Decide which strategies to improve vs add
   - Quarterly: Reassess target model parameters as capital grows

---

**Document Version:** 1.0
**Last Updated:** 2025-12-03
