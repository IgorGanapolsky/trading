# Research Infrastructure

This package provides the research infrastructure for systematic trading strategy development.

## Components

### 1. Factor Libraries (`factors/`)

Standardized feature engineering functions:

- **Returns** (`returns.py`): Multi-horizon returns, cumulative returns, rolling returns
- **Volatility** (`volatility.py`): Realized volatility, GARCH volatility, ATR
- **Volume/Flow** (`volume_flow.py`): Volume profile, VWAP deviation, OBV, VPT
- **Technicals** (`technicals.py`): RSI, MACD, Bollinger Bands, SMA, EMA, Stochastic
- **Cross-Sectional** (`cross_sectional.py`): Percentile ranks, z-scores, momentum, mean reversion

**Usage:**
```python
from src.research.factors import (
    calculate_multi_horizon_returns,
    calculate_realized_volatility,
    calculate_technical_indicators,
)

# Calculate features
returns = calculate_multi_horizon_returns(prices, horizons=['1d', '1w', '1mo'])
vol = calculate_realized_volatility(returns, window=20)
tech = calculate_technical_indicators(prices, volume)
```

### 2. Data Contracts (`data_contracts.py`)

Standardized data structures:

- **SignalSnapshot**: Feature vector at time t
- **FutureReturns**: Forward returns over multiple horizons
- **Label**: Supervised learning labels

**Usage:**
```python
from src.research.data_contracts import SignalSnapshot, FutureReturns

# Create signal snapshot
snapshot = SignalSnapshot(
    timestamp=pd.Timestamp('2024-01-01'),
    symbol='SPY',
    features=feature_series,
    metadata={'source': 'alpaca'}
)

# Create future returns
future = FutureReturns(
    symbol='SPY',
    timestamp=pd.Timestamp('2024-01-01'),
    returns_1d=0.02,
    returns_1w=0.05,
)
```

### 3. Labeling Pipeline (`labeling/`)

Reusable functions to create supervised learning targets:

- **Directional** (`directional.py`): Up/down labels over multiple horizons
- **Volatility** (`volatility.py`): Realized volatility labels
- **Triple-Barrier** (`triple_barrier.py`): Event-based labels

**Usage:**
```python
from src.research.labeling import (
    create_directional_labels,
    create_volatility_labels,
    create_triple_barrier_labels,
)

# Create directional labels
labels = create_directional_labels(returns, horizons=['1d', '1w'], threshold=0.01)

# Create triple-barrier labels
barrier_labels = create_triple_barrier_labels(
    prices,
    upper_barrier=0.02,
    lower_barrier=-0.01,
    max_holding_period=5
)
```

### 4. Research Workflow Templates (`notebooks/research_templates/`)

Standardized workflow for testing new ideas:

- **quick_test.py**: Template for "load data → engineer features → cross-validate → backtest → plot metrics"

**Usage:**
```python
from notebooks.research_templates.quick_test import run_research_experiment

results = run_research_experiment(
    model_class=MyModel,
    features=['returns_1d', 'rsi', 'macd'],
    target='returns_1d',
    train_start='2020-01-01',
    train_end='2023-01-01',
    test_start='2023-01-01',
    test_end='2024-01-01',
)
```

### 5. Canonical Baselines (`baselines/`)

Standard baseline strategies for benchmarking:

- **Buy-and-Hold** (`buy_and_hold.py`): Simplest possible strategy
- **Equal-Weight** (`equal_weight.py`): Equal allocation to all assets
- **SMA Cross** (`sma_cross.py`): Moving average crossover
- **Momentum** (`momentum.py`): Time-series and cross-sectional momentum

**Usage:**
```python
from src.research.baselines import BuyAndHoldStrategy, MomentumStrategy

# Buy-and-hold
bh = BuyAndHoldStrategy(symbols=['SPY', 'QQQ'])
signals = bh.generate_signals(data)

# Momentum
momentum = MomentumStrategy(lookback=20, method='time_series')
signals = momentum.generate_signals(data)
```

## Quick Start

1. **Engineer features:**
```python
from src.research.factors import calculate_technical_indicators
features = calculate_technical_indicators(prices, volume)
```

2. **Create labels:**
```python
from src.research.labeling import create_directional_labels
labels = create_directional_labels(returns, horizons=['1d'])
```

3. **Test against baselines:**
```python
from src.research.baselines import MomentumStrategy
baseline = MomentumStrategy()
baseline_signals = baseline.generate_signals(data)
```

## Next Steps

See `docs/WORLD_CLASS_AI_TRADING_GAP_ANALYSIS.md` for the complete roadmap.
