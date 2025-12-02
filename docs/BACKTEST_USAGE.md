# Backtest Engine Usage Guide

## Overview

The lightweight backtesting engine allows you to validate your trading strategies on historical data before deploying them in live trading. It simulates day-by-day strategy execution and provides comprehensive performance metrics.

## Quick Start

### Basic Usage

```python
from src.strategies.core_strategy import CoreStrategy
from src.backtesting.backtest_engine import BacktestEngine

# Create your strategy
strategy = CoreStrategy(
    daily_allocation=6.0,
    etf_universe=["SPY", "QQQ", "VOO"],
    use_sentiment=False  # Disable for faster backtesting
)

# Create backtest engine
engine = BacktestEngine(
    strategy=strategy,
    start_date="2025-09-01",
    end_date="2025-10-31",
    initial_capital=100000
)

# Run backtest
results = engine.run()

# Display report
print(results.generate_report())
```

### Hybrid Funnel Replay (Gate-by-Gate)

To mirror the production orchestrator inside your backtests, enable the hybrid gates:

```python
engine = BacktestEngine(
    strategy=strategy,
    start_date="2025-09-01",
    end_date="2025-10-31",
    initial_capital=100000,
    use_hybrid_gates=True,  # Momentum → Transformer RL → Sentiment proxy → Risk
    hybrid_options={"max_trades_per_day": 1},
)
```

When running the scenario matrix CLI you can toggle the same behaviour:

```bash
python3 scripts/run_backtest_matrix.py --use-hybrid-gates
```

This executes every scenario with the transformer-enabled Gate 2, the synthetic sentiment fallback, and the deterministic risk sizing logic. Telemetry artefacts include the explainability payloads so you can audit the RL gate offline.

## Features

### 1. BacktestEngine

The main engine that simulates strategy execution:

- **Simulates daily trading** on historical data
- **Tracks portfolio value** throughout the backtest period
- **Calculates performance metrics** (Sharpe, drawdown, win rate)
- **Uses yfinance** for historical price data
- **Reuses existing strategy** - works with CoreStrategy

#### Key Methods

```python
# Run the backtest
results = engine.run()

# Access internals
trading_dates = engine._get_trading_dates()
portfolio_value = engine.portfolio_value
current_positions = engine.positions
```

### 2. BacktestResults

Comprehensive results data structure:

```python
results = engine.run()

# Access metrics
print(f"Total Return: {results.total_return}%")
print(f"Sharpe Ratio: {results.sharpe_ratio}")
print(f"Max Drawdown: {results.max_drawdown}%")
print(f"Win Rate: {results.win_rate}%")
print(f"Total Trades: {results.total_trades}")

# Generate human-readable report
report = results.generate_report()

# Export to dictionary (for JSON serialization)
results_dict = results.to_dict()
```

## Example: 60-Day Backtest

```python
from datetime import datetime, timedelta
from src.strategies.core_strategy import CoreStrategy
from src.backtesting.backtest_engine import BacktestEngine

# Calculate 60-day period
end_date = datetime.now()
start_date = end_date - timedelta(days=90)  # ~60 trading days

# Setup
strategy = CoreStrategy(daily_allocation=6.0, use_sentiment=False)
engine = BacktestEngine(
    strategy=strategy,
    start_date=start_date.strftime("%Y-%m-%d"),
    end_date=end_date.strftime("%Y-%m-%d"),
    initial_capital=100000.0
)

# Execute
results = engine.run()

# Review
print(results.generate_report())
print(f"\nFinal Capital: ${results.final_capital:,.2f}")
print(f"Total Return: {results.total_return:.2f}%")
```

## Performance Metrics Explained

### Total Return
- Percentage gain/loss from initial capital
- Formula: `(Final Capital - Initial Capital) / Initial Capital * 100`

### Sharpe Ratio
- Risk-adjusted return metric
- Values > 1.0 = good, > 1.5 = very good, > 2.0 = excellent
- Accounts for volatility of returns

### Max Drawdown
- Largest peak-to-trough decline
- Lower is better (< 10% is good for this strategy)
- Measures worst-case scenario

### Win Rate
- Percentage of profitable days
- Target: > 55% for consistent profitability
- Strategy should aim for 60%+ win rate

### Annualized Return
- Total return extrapolated to annual basis
- Useful for comparing strategies of different durations

## Testing

Run the simple test suite to verify installation:

```bash
python test_backtest_simple.py
```

This will:
1. Test BacktestResults data structure
2. Test BacktestEngine initialization
3. Display usage instructions

## Notes

- **Disable sentiment analysis** (`use_sentiment=False`) for faster backtesting
- **Paper trading mode** is automatically used (no real orders)
- **Historical data** is fetched from yfinance (requires internet)
- **Weekdays only** - automatically filters to trading days
- **Performance** - Expect ~5 minutes for 60-day backtest

## File Structure

```
src/backtesting/
├── __init__.py           # Package initialization
├── backtest_engine.py    # Main backtesting engine
└── backtest_results.py   # Results data structure
```

## Integration with Existing Strategy

The backtest engine is designed to work seamlessly with `CoreStrategy`:

```python
# CoreStrategy methods used by backtest engine:
strategy.daily_allocation         # How much to invest daily
strategy.etf_universe            # List of ETFs to trade
strategy._get_market_sentiment() # Market sentiment (optional)
```

The engine simulates what would happen if you ran your strategy every day during the backtest period.

## Success Criteria

Before going live, your strategy should meet these criteria in backtesting:

- ✓ **Total Return** > 5% (for 60-day period)
- ✓ **Sharpe Ratio** > 1.0
- ✓ **Max Drawdown** < 10%
- ✓ **Win Rate** > 55%
- ✓ **Consistent profitability** (no critical bugs)

## Example Output

```
================================================================================
BACKTEST RESULTS SUMMARY
================================================================================

PERIOD INFORMATION
--------------------------------------------------------------------------------
Start Date:        2025-09-01
End Date:          2025-10-31
Trading Days:      60

CAPITAL & RETURNS
--------------------------------------------------------------------------------
Initial Capital:   $100,000.00
Final Capital:     $106,250.00
Total Return:      $6,250.00 (6.25%)
Annualized Return: 38.75%

RISK METRICS
--------------------------------------------------------------------------------
Sharpe Ratio:      1.75
Max Drawdown:      4.50%
Volatility:        8.20%

TRADE STATISTICS
--------------------------------------------------------------------------------
Total Trades:      60
Profitable Trades: 36
Losing Trades:     24
Win Rate:          60.00%
Avg Trade Return:  0.10%

PERFORMANCE SUMMARY
--------------------------------------------------------------------------------
Overall Rating:    GOOD
```

## Troubleshooting

### "No module named 'pandas'"
Install dependencies: `pip install pandas numpy yfinance`

### "Insufficient data for symbol"
Ensure your backtest period has enough historical data available

### Slow performance
- Reduce backtest period (fewer days)
- Disable sentiment analysis (`use_sentiment=False`)
- Reduce ETF universe size

## Next Steps

1. Run backtest on your strategy
2. Analyze results report
3. Tune strategy parameters if needed
4. Re-run backtest to validate improvements
5. Once metrics meet success criteria → deploy to paper trading
6. After 30+ days of successful paper trading → consider live trading

---

Created: 2025-11-02
Version: 1.0
