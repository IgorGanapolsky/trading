# Lesson Learned #032: ML Experiment Automation for Trading Research

**Date**: December 14, 2025
**Category**: ML / Infrastructure
**Severity**: HIGH (enables systematic strategy optimization)
**Status**: IMPLEMENTED

## Executive Summary

Implemented ML experiment automation module inspired by Anthropic's approach of running 1000+ experiments/day. Enables systematic hyperparameter sweeps, backtests, and model comparisons with parallel execution, caching, and automated analysis.

## Problem

Manual strategy optimization is:
- Slow: Testing one parameter set at a time
- Error-prone: Easy to miss combinations
- Not systematic: Hard to compare results
- Not reproducible: No automatic caching/logging

Without automation, we can only test ~10-20 parameter sets manually.

## Research: Anthropic's ML Experiment Approach

From Anthropic engineering:
> "Without Claude, about 27% of the work Anthropic engineers are now doing simply would not have been done at all - including building tools to perform small code fixes that they might not have bothered remediating previously."

Key insight: Automate experiment running so you can explore more of the parameter space.

## Solution

Created `src/experiments/` module with:

### 1. HyperparameterGrid

```python
grid = HyperparameterGrid({
    "rsi_period": [7, 14, 21],
    "stop_loss_pct": [1.5, 2.0, 2.5, 3.0],
    "take_profit_pct": [3.0, 4.0, 5.0],
})

# Full grid: 3 * 4 * 3 = 36 combinations
combos = grid.get_combinations(mode="grid")

# Random sample for large grids
combos = grid.get_combinations(mode="random", n_samples=100)
```

### 2. ExperimentRunner

```python
runner = ExperimentRunner()

results = await runner.run_sweep(
    experiment_fn=rsi_strategy_backtest,
    grid=grid,
    parallel=True,      # Run in parallel
    max_workers=4,      # 4 concurrent experiments
)

# Find best parameters
best = runner.get_best_result(results, metric="sharpe_ratio")
print(f"Best params: {best.params}")
print(f"Sharpe: {best.metrics['sharpe_ratio']}")

# Generate report
report = runner.generate_report(results)
```

### 3. Pre-built Trading Experiments

```python
from src.experiments.trading_experiments import (
    rsi_strategy_backtest,
    macd_strategy_backtest,
    combined_strategy_backtest,
    RSI_PARAMETER_GRID,
    MACD_PARAMETER_GRID,
)

# Run RSI optimization
results, report = await run_rsi_optimization(max_experiments=100)
```

## Key Features

| Feature | Benefit |
|---------|---------|
| Parallel execution | 4-8x faster with multi-core |
| Result caching | Skip completed experiments on re-run |
| Automatic checkpointing | Resume interrupted sweeps |
| Parameter importance | Identify which params matter most |
| Report generation | Automated analysis and ranking |
| CSV/JSON export | For external analysis |

## Pre-defined Parameter Grids

### RSI Strategy (1,024 combinations)
- rsi_period: [7, 10, 14, 21]
- oversold: [20, 25, 30, 35]
- overbought: [65, 70, 75, 80]
- stop_loss_pct: [1.5, 2.0, 2.5, 3.0]
- take_profit_pct: [3.0, 4.0, 5.0, 6.0]

### MACD Strategy (144 combinations)
- macd_fast: [8, 10, 12, 14]
- macd_slow: [21, 26, 30]
- macd_signal: [7, 9, 11]
- stop_loss_pct: [1.5, 2.0, 2.5, 3.0]

### Combined Strategy (59,049 combinations)
- Full RSI + MACD parameters
- Use random sampling (mode="random")

## Output Metrics

Each backtest returns:
- `total_return`: Total P/L percentage
- `sharpe_ratio`: Risk-adjusted return (annualized)
- `sortino_ratio`: Downside-only risk adjustment
- `win_rate`: Percentage of winning trades
- `profit_factor`: Gross profit / gross loss
- `max_drawdown`: Maximum peak-to-trough decline
- `num_trades`: Total trade count
- `avg_bars_held`: Average holding period

## Example Report

```
======================================================================
ML EXPERIMENT SWEEP REPORT
======================================================================

SUMMARY
----------------------------------------
  Total Experiments: 100
  Completed: 98
  Failed: 0
  Skipped (cached): 2

METRIC RANGES
----------------------------------------
  sharpe_ratio         min=-1.2341  max=2.1543  avg=0.4521
  total_return         min=-15.23   max=28.45   avg=5.67
  win_rate             min=0.35     max=0.68    avg=0.52

TOP 5 BY SHARPE_RATIO
----------------------------------------
  1. sharpe_ratio=2.1543 | rsi_period=14, oversold=30, stop_loss=2.0
  2. sharpe_ratio=1.9876 | rsi_period=10, oversold=25, stop_loss=2.5
  ...

PARAMETER IMPACT
----------------------------------------
  rsi_period           impact=+0.4521 (best=14, worst=7)
  stop_loss_pct        impact=+0.2134 (best=2.0, worst=3.0)
  oversold             impact=+0.1567 (best=30, worst=20)

TIMING
----------------------------------------
  Total Time: 45.2s (0.8m)
  Avg per Experiment: 0.46s
  Throughput: 130.4 experiments/min
```

## Usage Patterns

### Quick Parameter Check
```python
# Test 10 random combinations
results, _ = await run_experiment_sweep(
    experiment_fn=rsi_strategy_backtest,
    params={"rsi_period": [7, 14, 21], "oversold": [25, 30, 35]},
    mode="random",
    n_samples=10,
)
```

### Full Optimization
```python
# Run 500 experiments on combined strategy
results, report = await run_full_optimization(max_experiments=500)
print(report)
```

### Custom Experiment
```python
def my_strategy(params):
    # Your backtest logic
    return {"sharpe": 1.5, "return": 10.0}

grid = HyperparameterGrid({"param1": [1, 2, 3], "param2": ["a", "b"]})
results = await runner.run_sweep(my_strategy, grid)
```

## Files Created

- `src/experiments/__init__.py`
- `src/experiments/experiment_runner.py` (450 lines)
- `src/experiments/trading_experiments.py` (400 lines)
- `tests/test_experiments.py` (300 lines)

## Expected Impact

| Metric | Before | After |
|--------|--------|-------|
| Experiments/day | ~20 manual | 1000+ automated |
| Parameter coverage | 5-10% | 100% (or sampled) |
| Reproducibility | Low | Full caching |
| Analysis time | Hours | Minutes |

## Integration Points

1. **Strategy Development**: Optimize before deploying
2. **Skill Library**: Best params become skills
3. **HICRA**: Identify which params affect strategic decisions
4. **Observability**: Track experiment costs

## Tags

#experiments #hyperparameter #optimization #backtest #automation #ml
