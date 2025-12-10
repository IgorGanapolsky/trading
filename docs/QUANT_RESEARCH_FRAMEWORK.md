# Quant Research Framework

This document describes the quantitative research framework implemented in `src/research/`, providing a world-class infrastructure for alpha research, strategy development, and model validation.

## Overview

The research framework addresses key gaps identified in building a world-class AI trading system:

1. **Strategy Research Layer**: Structured alpha research with feature libraries
2. **Data Labeling Pipeline**: Triple-barrier and multi-horizon target creation
3. **Data Contracts**: Schema validation and quality checks
4. **Experiment Tracking**: Reproducible model development
5. **Portfolio Construction**: Multiple optimization methods
6. **Canonical Baselines**: Performance benchmarks for model validation
7. **Factor Analysis**: Risk decomposition and exposure tracking

## Quick Start

```python
from src.research import (
    AlphaResearcher,
    TripleBarrierLabeler,
    DataValidator,
    ExperimentTracker,
    PortfolioOptimizer,
    run_baseline_comparison,
    FactorModel,
)

# 1. Validate data quality
validator = DataValidator()
report = validator.validate(df, symbol="SPY")
if report.overall_status.value == "critical":
    raise ValueError(f"Data quality issues: {report}")

# 2. Generate features
from src.research.alpha import FeatureLibrary
feature_lib = FeatureLibrary()
features = feature_lib.compute_all_features(df)

# 3. Create labels
labeler = TripleBarrierLabeler()
labels = labeler.fit_transform(df)

# 4. Run experiment
tracker = ExperimentTracker()
config = ExperimentConfig(
    name="momentum_model",
    hyperparameters={"hidden_dim": 128, "learning_rate": 0.001}
)
run = tracker.start_run("momentum_model", config)
tracker.log_metrics({"sharpe": 1.5, "max_dd": 0.10})
tracker.end_run()

# 5. Check vs baselines
baseline_results = run_baseline_comparison(df)
# Model must beat these to be worth deploying!
```

## Module Reference

### 1. Alpha Research (`src/research/alpha.py`)

Provides a comprehensive feature library for alpha research:

#### Feature Categories
- **Returns**: Multi-horizon returns, log returns, risk-adjusted returns
- **Volatility**: Realized vol, Parkinson, Garman-Klass, regime indicators
- **Volume**: Volume momentum, VWAP deviation, accumulation/distribution
- **Technicals**: MACD, RSI, Bollinger, ATR, ADX, stochastic
- **Cross-sectional**: Ranks, z-scores, sector-relative metrics
- **Microstructure**: Bid-ask spread, order imbalance

#### Usage
```python
from src.research.alpha import FeatureLibrary, AlphaResearcher

# Generate features
feature_lib = FeatureLibrary()
features = feature_lib.compute_all_features(df)

# Generate alpha signals
researcher = AlphaResearcher(feature_lib)
signals = researcher.generate_signals(
    features,
    ["momentum", "mean_reversion", "trend_following"]
)

# Rank signals by predictive power
rankings = researcher.rank_signals(signals, forward_returns)

# Combine alphas
combined = researcher.combine_alphas(signals, weights=[0.5, 0.3, 0.2])
```

### 2. Data Labeling (`src/research/labeling.py`)

Creates supervised learning targets following best practices:

#### Triple-Barrier Method
```python
from src.research.labeling import TripleBarrierLabeler, TripleBarrierConfig

config = TripleBarrierConfig(
    profit_taking_multiplier=2.0,  # ATR multiplier for take-profit
    stop_loss_multiplier=1.0,       # ATR multiplier for stop-loss
    max_holding_days=10,            # Maximum holding period
    use_dynamic_barriers=True,      # ATR-based barriers
)

labeler = TripleBarrierLabeler(config)
result = labeler.fit_transform(df)

# Labels: 1 (profit), -1 (loss), 0 (time barrier)
labels = result.labels
```

#### Directional Labels
```python
from src.research.labeling import DirectionalLabeler

labeler = DirectionalLabeler(horizons=[1, 5, 10, 21])
result = labeler.fit_transform(df)

# Binary labels for each horizon
direction_5d = result.labels["direction_5d"]
```

### 3. Data Contracts (`src/research/data_contracts.py`)

Ensures data quality and reproducibility:

#### Validation
```python
from src.research.data_contracts import DataValidator, OHLCVSchema

validator = DataValidator(
    max_gap_days=5,
    max_price_change_pct=50.0,
    min_volume=1000,
)

report = validator.validate(df, symbol="SPY")
print(f"Status: {report.overall_status}")
print(f"Passed: {report.passed_checks}/{report.total_checks}")

# Check specific issues
for result in report.results:
    if not result.passed:
        print(f"FAILED: {result.check_name} - {result.message}")
```

#### Data Snapshots
```python
from src.research.data_contracts import DataSnapshot

snapshot = DataSnapshot(storage_dir="data/snapshots")

# Save versioned snapshot
snapshot_id = snapshot.save_snapshot(
    df,
    symbol="SPY",
    description="Training data for momentum model",
    metadata={"source": "alpaca", "adjusted": True}
)

# Load for reproducibility
df_loaded, manifest = snapshot.load_snapshot(snapshot_id)
```

### 4. Experiment Tracking (`src/research/experiments.py`)

Track experiments for reproducibility:

```python
from src.research.experiments import ExperimentTracker, ExperimentConfig

tracker = ExperimentTracker(tracking_dir="data/experiments")

config = ExperimentConfig(
    name="lstm_momentum",
    description="LSTM model for momentum prediction",
    tags=["lstm", "momentum"],
    hyperparameters={
        "hidden_dim": 128,
        "num_layers": 2,
        "learning_rate": 0.001,
    },
    data_config={
        "symbol": "SPY",
        "start_date": "2020-01-01",
    }
)

# Start experiment
run = tracker.start_run("momentum_experiment", config, data_snapshot_id="...")

# Log metrics
tracker.log_metric("train_loss", 0.025)
tracker.log_metric("sharpe", 1.45)
tracker.log_metric("max_drawdown", 0.12)

# Save model
tracker.log_model(model, "momentum_lstm")

# End experiment
tracker.end_run("completed")

# Compare experiments
comparison = tracker.compare_runs(run_ids, metrics=["sharpe", "max_drawdown"])
```

### 5. Portfolio Construction (`src/research/portfolio.py`)

Multiple optimization methods:

```python
from src.research.portfolio import (
    PortfolioOptimizer,
    PortfolioConstraints,
    OptimizationMethod,
)

constraints = PortfolioConstraints(
    min_weight=0.0,           # Long-only
    max_weight=0.20,          # Max 20% in single position
    max_turnover=0.50,        # Max 50% turnover per rebalance
    target_volatility=0.15,   # 15% annual vol target
    max_positions=20,
)

optimizer = PortfolioOptimizer(constraints=constraints)

# Mean-Variance Optimization
result = optimizer.optimize(
    expected_returns,
    covariance_matrix,
    method=OptimizationMethod.MEAN_VARIANCE,
)

# Risk Parity
result_rp = optimizer.optimize(
    expected_returns,
    covariance_matrix,
    method=OptimizationMethod.RISK_PARITY,
)

# Kelly Criterion (half-Kelly)
result_kelly = optimizer.optimize(
    expected_returns,
    covariance_matrix,
    method=OptimizationMethod.KELLY,
)
```

### 6. Canonical Baselines (`src/research/baselines.py`)

Every model must beat these:

```python
from src.research.baselines import (
    run_baseline_comparison,
    check_model_beats_baselines,
)

# Run all baselines
baseline_results = run_baseline_comparison(df)

# Check if model beats baselines
comparison = check_model_beats_baselines(
    model_result,
    baseline_results,
    min_sharpe_improvement=0.1,
)

print(f"Beats all baselines: {comparison['beats_all_baselines']}")
print(f"Recommendation: {comparison['recommendation']}")
```

**Built-in Baselines:**
- Buy and Hold
- Moving Average Crossover (20/50, 50/200)
- Time-Series Momentum (126d, 252d)
- Mean Reversion (20d, z=2)
- RSI Mean Reversion
- Volatility Breakout

### 7. Factor Analysis (`src/research/factors.py`)

Understand portfolio exposures:

```python
from src.research.factors import (
    FactorModel,
    SyntheticFactorGenerator,
    FactorRiskMonitor,
)

# Generate synthetic factors from prices
factor_gen = SyntheticFactorGenerator()
factor_returns = factor_gen.generate_all_factors(prices, market_symbol="SPY")

# Factor model
factor_model = FactorModel()
factor_model.set_factor_returns(factor_returns)

# Calculate exposures
exposures = factor_model.calculate_exposures(portfolio_returns)
for name, exp in exposures.items():
    print(f"{name}: β={exp.exposure:.3f} (t={exp.t_stat:.2f})")

# Factor attribution
attribution = factor_model.attribute_returns(portfolio_returns)
print(f"Alpha: {attribution.alpha:.2%}")
print(f"Factor contributions: {attribution.factor_contributions}")

# Monitor exposures
monitor = FactorRiskMonitor(factor_model)
breaches = monitor.check_exposure_limits({
    "market": (-0.5, 1.5),
    "momentum": (-0.5, 0.5),
})
```

## Research Workflow

### 1. Data Preparation
```
Raw Data → Validation → Snapshot → Features → Labels
```

### 2. Alpha Research
```
Features → Signal Generation → Signal Ranking → Alpha Combination
```

### 3. Model Development
```
Start Experiment → Train Model → Validate → Log Metrics → Compare Baselines
```

### 4. Portfolio Construction
```
Alpha Signals → Expected Returns → Optimization → Constraints → Final Weights
```

### 5. Risk Analysis
```
Portfolio Returns → Factor Exposures → Attribution → Monitoring → Alerts
```

## Best Practices

### 1. Always Validate Data
```python
report = validator.validate(df)
assert report.overall_status.value != "critical"
```

### 2. Use Walk-Forward Validation
```python
from src.ml.walk_forward_validator import WalkForwardValidator
validator = WalkForwardValidator(train_window=252, test_window=63)
results = validator.validate(symbol, model_class, model_kwargs, data_processor)
```

### 3. Beat Baselines Before Deploying
```python
comparison = check_model_beats_baselines(model_result, baseline_results)
if not comparison['beats_all_baselines']:
    raise ValueError(comparison['recommendation'])
```

### 4. Track Experiments
```python
# Every experiment should have:
# - Git SHA
# - Data snapshot ID
# - Full hyperparameters
# - All performance metrics
```

### 5. Monitor Factor Exposures
```python
# Set and enforce limits
limits = {"market": (0.8, 1.2), "momentum": (-0.3, 0.3)}
breaches = monitor.check_exposure_limits(limits)
```

## Files and Structure

```
src/research/
├── __init__.py          # Package exports
├── alpha.py             # Feature library and alpha research
├── labeling.py          # Triple-barrier and directional labels
├── data_contracts.py    # Validation and snapshots
├── experiments.py       # Experiment tracking
├── portfolio.py         # Portfolio optimization
├── baselines.py         # Canonical baseline strategies
└── factors.py           # Factor analysis
```

## Integration with Existing System

The research package integrates with existing modules:

- **Backtesting**: Use `src/backtesting/backtest_engine.py` with research features
- **ML Models**: Use `src/ml/` models with experiment tracking
- **Risk Management**: Use `src/risk/` with factor monitoring
- **Strategies**: Use `src/strategies/` with portfolio optimization

## References

- López de Prado, M. (2018). *Advances in Financial Machine Learning*
- Fama, E. F., & French, K. R. (1993). Common risk factors
- Carhart, M. M. (1997). Momentum factor
- Grinold, R. C., & Kahn, R. N. (2000). *Active Portfolio Management*

---

*Created: 2025-12-02*
*Last Updated: 2025-12-02*
