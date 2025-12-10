# Metrics Clarification

**Created**: 2025-12-05
**Purpose**: Clarify the difference between metrics and correct historical misstatements.

## Win Rate Metrics

There are TWO types of win rate in this system:

### 1. Daily Win Rate (what backtests report)
- **Definition**: Percentage of DAYS that are profitable
- **Calculation**: (Days with positive P/L) / (Total trading days) * 100
- **Current range**: 38-52% across backtest scenarios
- **Location**: `backtest_results.win_rate`

### 2. Trade Win Rate (more accurate for strategy evaluation)
- **Definition**: Percentage of TRADES that are profitable
- **Calculation**: (Winning trades) / (Total closed trades) * 100
- **Current status**: 0% (no trades have been closed in live trading)
- **Location**: `backtest_results.trade_metrics.trade_win_rate`

## Correcting the 62.2% Claim

The "62.2% win rate, 2.18 Sharpe ratio" claim that appeared in various files was **NOT accurate**:

| Claim | Reality |
|-------|---------|
| 62.2% win rate | 38-52% across 6 scenarios |
| 2.18 Sharpe ratio | -7 to -72 (all negative) |
| Source | Single Nov 7 backtest | Comprehensive Dec 2 matrix |

### What happened:
1. Nov 7, 2025: A single backtest of SPY/QQQ/VOO showed 62.2% daily win rate
2. This result was propagated to feature_list.json and system_state.json
3. Dec 2, 2025: Comprehensive 6-scenario matrix revealed much lower performance
4. Dec 5, 2025: Corrections applied to documentation

### Where the 62.2% appeared (now corrected):
- ~~feature_list.json~~ - Updated with accurate note
- ~~system_state.json notes~~ - Added backtest_reality section
- User prompt hook - Shows 0% live win rate (correct - no closed trades)

## Actual Backtest Results (Dec 2, 2025)

From `data/backtests/latest_summary.json`:

| Scenario | Win Rate | Sharpe | Status |
|----------|----------|--------|--------|
| Bull Run 2024 | 51.56% | -72.35 | Needs Improvement |
| COVID Whiplash 2020 | 52.94% | -13.82 | Needs Improvement |
| Inflation Shock 2022 | 41.54% | -40.87 | Needs Improvement |
| Weekend Crypto 2023 | 38.24% | -28.52 | Needs Improvement |
| Holiday Regime 2024 | 46.95% | -7.41 | Needs Improvement |
| High Vol Q4 2022 | 38.46% | -65.69 | Needs Improvement |

**All 6 scenarios show negative Sharpe ratios**, indicating the strategy needs significant improvement before scaling capital.

## Live Trading Performance

As of Day 9 (Dec 5, 2025):
- Total trades: 7
- Closed trades: 0
- Trade win rate: 0% (cannot calculate - no exits)
- Portfolio P/L: +$5.50 (+0.0055%)

The position manager was updated on Dec 3, 2025 with 3% exit thresholds. Once positions start closing, we'll have accurate trade-level win rate data.

## Recommended Actions

1. **Wait for 30+ closed trades** before drawing conclusions about live performance
2. **Use comprehensive backtest matrix** (not single-scenario results) for strategy evaluation
3. **Focus on trade win rate** (not daily win rate) for accurate performance assessment
4. **Do not scale capital** until Sharpe ratio is consistently positive

## File References

- `data/backtests/latest_summary.json` - Comprehensive backtest results
- `src/backtesting/backtest_results.py:36-37` - TradeMetrics class with trade_win_rate
- `src/backtesting/backtest_engine.py:829-830` - Daily win rate calculation
