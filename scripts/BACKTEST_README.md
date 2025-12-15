# Crypto Strategy Backtest Comparison

## Overview

`backtest_crypto_strategy.py` is a standalone Python script that compares the performance of two crypto trading strategies over the past 90 days:

### v3.0: Fear & Greed Strategy
- **Entry Rule**: Buy when Fear & Greed Index < 25 (Extreme Fear)
- **No Filters**: No 50-day MA check, no RSI momentum check
- **Philosophy**: Contrarian - buy the dips during extreme fear

### v4.1: Trend + Momentum Strategy
- **Entry Rules**:
  - Price > 50-day MA (trend filter)
  - AND RSI > 50 (momentum confirmation)
- **Fear & Greed**: Used for position sizing only (not timing)
- **Philosophy**: Trend-following - only buy when uptrend confirmed

## Features

- ✅ Historical data from yfinance (BTC, ETH, SOL)
- ✅ Fear & Greed Index integration
- ✅ RSI and 50-day MA calculation
- ✅ Stop-loss (7%) and Take-profit (10%) management
- ✅ Detailed trade logging
- ✅ Comprehensive metrics:
  - Total Return (%)
  - Max Drawdown (%)
  - Win Rate (%)
  - Sharpe Ratio
  - Number of Trades
  - Average Trade P/L

## Installation

Install required dependencies:

```bash
pip install numpy pandas yfinance requests
```

Or use project requirements:

```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

```bash
python3 scripts/backtest_crypto_strategy.py
```

### Expected Output

```
====================================================================================================
🚀 CRYPTO STRATEGY BACKTEST: v3.0 (Fear & Greed) vs v4.1 (Trend + Momentum)
====================================================================================================

⚙️  Configuration:
   - Initial Capital: $1,000.00
   - Daily Amount: $25.00
   - Lookback Period: 90 days
   - Stop Loss: 7%
   - Take Profit: 10%
   - Symbols: BTC-USD, ETH-USD, SOL-USD

📊 Fetching 90 days of historical data...
   ✅ BTC-USD: 150 bars
   ✅ ETH-USD: 150 bars
   ✅ SOL-USD: 150 bars

😱 Fetching Fear & Greed Index history...
   ✅ Fetched 90 days of Fear & Greed data

====================================================================================================
🔵 BACKTESTING v3.0: Fear & Greed Strategy (No Filters)
====================================================================================================

📅 2024-12-01: Fear & Greed = 22 (EXTREME FEAR)
   🟢 BUY 0.000456 BTC-USD @ $54,800.00

...

====================================================================================================
🟢 BACKTESTING v4.1: Trend + Momentum Strategy
====================================================================================================

📅 2024-12-05: BTC-USD - Price $56,000, MA50 $55,200, RSI 58
   📊 Fear & Greed 35 (Fear) -> 1.25x position
   🟢 BUY 0.000558 BTC-USD @ $56,000.00

...

====================================================================================================
📊 BACKTEST COMPARISON: v3.0 vs v4.1
====================================================================================================

Metric                         v3.0 (Fear & Greed)       v4.1 (Trend + Momentum)   Winner
----------------------------------------------------------------------------------------------------
Initial Capital                $  1,000.00               $  1,000.00               —
Final Capital                  $  1,045.00               $  1,120.00               v4.1 ✓
Total Return                       4.50%                     12.00%                v4.1 ✓
Max Drawdown                       8.50%                      5.20%                v4.1 ✓
Win Rate                          55.0%                      68.0%                v4.1 ✓
Sharpe Ratio                       0.45                       0.78                v4.1 ✓
Number of Trades                     12                          8                —
Avg Trade P/L                    $ 3.75                     $ 15.00               v4.1 ✓
----------------------------------------------------------------------------------------------------

OVERALL WINNER:               v3.0 (1 metrics)          v4.1 (6 metrics)          🏆 v4.1 WINS!
====================================================================================================

💾 Results saved:
   - data/backtests/backtest_v3.0_results.json
   - data/backtests/backtest_v4.1_results.json

✅ Backtest complete!
```

## Output Files

The script saves detailed results to JSON files:

- `data/backtests/backtest_v3.0_results.json` - v3.0 strategy results
- `data/backtests/backtest_v4.1_results.json` - v4.1 strategy results

Each file contains:
- Strategy metadata
- Performance metrics
- All trades with timestamps, prices, and reasons

## Configuration

Edit the `BacktestConfig` class to customize:

```python
config = BacktestConfig(
    initial_capital=1000.0,      # Starting capital
    daily_amount=25.0,            # Daily investment amount
    lookback_days=90,             # Backtest period
    stop_loss_pct=0.07,          # 7% stop-loss
    take_profit_pct=0.10,        # 10% take-profit
    symbols=["BTC-USD", "ETH-USD", "SOL-USD"]  # Cryptos to test
)
```

## How It Works

### v3.0 Backtest Logic

1. **Daily Loop**: Iterate through last 90 days
2. **Fear & Greed Check**: If FG < 25 (Extreme Fear)
3. **Select Best Crypto**: Choose coin with highest 7-day momentum
4. **Buy**: Execute $25 purchase (no filters)
5. **Risk Management**: Check stop-loss (-7%) and take-profit (+10%)
6. **Repeat**: Next day

### v4.1 Backtest Logic

1. **Daily Loop**: Iterate through last 90 days
2. **Filter Check**: For each crypto:
   - Is price > 50-day MA? ✅
   - Is RSI > 50? ✅
3. **Skip if No Valid Cryptos**: Wait for better setup
4. **Select Best**: Choose crypto with highest momentum (from valid list)
5. **Position Sizing**: Adjust size based on Fear & Greed:
   - FG ≤ 25: 1.5x position
   - FG ≤ 40: 1.25x position
   - FG ≥ 75: Skip (extreme greed)
6. **Buy**: Execute purchase
7. **Risk Management**: Check stop-loss and take-profit
8. **Repeat**: Next day

## Interpreting Results

### What to Look For

1. **Total Return**: Higher is better (v4.1 should typically win due to trend-following)
2. **Max Drawdown**: Lower is better (v4.1 should have less risk due to filters)
3. **Win Rate**: Higher is better (v4.1 should have more winners by avoiding bad setups)
4. **Sharpe Ratio**: Higher is better (risk-adjusted returns)
5. **Number of Trades**: More trades ≠ better (v4.1 should be more selective)

### Expected Outcome

Based on research and strategy design:

- **v4.1 should win** in most market conditions
- **v3.0 may outperform** during extreme bear markets (buying every dip)
- **v4.1 has better risk management** (skips falling knives)
- **v3.0 has more trades** (buys more frequently)

## Troubleshooting

### "ModuleNotFoundError: No module named 'pandas'"

Install dependencies:
```bash
pip install numpy pandas yfinance requests
```

### "Unable to fetch data for BTC-USD"

- Check internet connection
- yfinance API may be rate-limited (wait and retry)
- Try reducing lookback period

### "No Fear & Greed data available"

The script will fall back to simulated data if the API is unavailable. This won't affect the backtest validity (just for demonstration).

## Related Files

- `/home/user/trading/src/strategies/crypto_strategy.py` - Production crypto strategy
- `/.github/workflows/weekend-crypto-trading.yml` - Live v4.1 implementation
- `/home/user/trading/docs/r-and-d-phase.md` - Strategy research documentation

## Development Notes

### Why 90 Days?

- Sufficient sample size for statistical significance
- Captures 1-2 crypto market cycles
- Matches R&D phase timeline (Day 9/90)

### Why These Metrics?

- **Total Return**: Core profitability measure
- **Max Drawdown**: Risk management effectiveness
- **Win Rate**: Strategy reliability
- **Sharpe Ratio**: Risk-adjusted performance (industry standard)

### Future Enhancements

- [ ] Add buy-and-hold baseline comparison
- [ ] Support custom date ranges
- [ ] Add Monte Carlo simulation
- [ ] Export results to CSV/Excel
- [ ] Add visualization (equity curves, drawdown charts)
- [ ] Test on different market regimes (bull, bear, sideways)

## Citation

```bibtex
@software{crypto_backtest_2025,
  title={Crypto Strategy Backtest Comparison Tool},
  author={Igor Ganapolsky and Claude},
  year={2025},
  version={1.0},
  url={https://github.com/iganapolsky/trading}
}
```

## License

Same as parent project.
