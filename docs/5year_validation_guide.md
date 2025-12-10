# 5-Year Walk-Forward Validation Guide

## Overview

The 5-year walk-forward validation script (`scripts/run_5year_validation.py`) provides comprehensive out-of-sample testing to determine if a trading strategy has a real edge. This is the gold standard validation before deploying capital.

## Why Walk-Forward Validation?

Walk-forward validation prevents overfitting by:
1. **Time-aware splitting**: Training data always comes before test data (no look-ahead bias)
2. **Multiple test periods**: Strategy is tested on many unseen periods
3. **Overfitting detection**: Compares in-sample vs out-of-sample performance
4. **Regime awareness**: Tests performance across different market conditions

## Validation Structure

```
5 years of data (2019-2024)
├── Window 1: Train on 2019, Test on Q1 2020
├── Window 2: Train on 2019-Q1 2020, Test on Q2 2020
├── Window 3: Train on 2019-Q2 2020, Test on Q3 2020
└── Window N: Train on 2019-2023, Test on Q4 2024
```

**Configuration:**
- Train Window: 252 trading days (~1 year)
- Test Window: 63 trading days (~1 quarter)
- Step Size: 63 days (rolling forward 1 quarter)
- Expected Folds: ~16 folds for 5-year period

## Usage

### Basic Usage (5 years, 2019-2024)

```bash
python scripts/run_5year_validation.py
```

This runs validation on the default 5-year period with core ETFs (SPY, QQQ, IWM, VOO, VTI).

### Custom Date Range

```bash
python scripts/run_5year_validation.py --start 2018-01-01 --end 2023-12-31
```

### Custom Symbols

```bash
python scripts/run_5year_validation.py --symbols SPY QQQ DIA
```

### Custom Parameters

```bash
python scripts/run_5year_validation.py \
  --start 2019-01-01 \
  --end 2024-12-31 \
  --daily-allocation 15.0 \
  --initial-capital 50000.0
```

### Quick Test Mode

For faster validation (uses larger step size):

```bash
python scripts/run_5year_validation.py --quick
```

### All Options

```bash
python scripts/run_5year_validation.py --help
```

**Available options:**
- `--start`: Start date (default: 2019-01-01)
- `--end`: End date (default: 2024-12-31)
- `--symbols`: List of symbols (default: SPY QQQ IWM VOO VTI)
- `--daily-allocation`: Daily allocation in dollars (default: 10.0)
- `--initial-capital`: Initial capital (default: 100000.0)
- `--quick`: Quick test mode (faster, fewer windows)
- `--output-dir`: Output directory (default: reports)

## Output Files

The script generates three files in the `reports/` directory:

1. **JSON Results** (`walk_forward_5year_YYYYMMDD_HHMMSS.json`)
   - Complete validation data
   - All window results
   - Regime performance breakdown
   - Machine-readable format

2. **Text Report** (`walk_forward_5year_YYYYMMDD_HHMMSS.txt`)
   - Human-readable comprehensive report
   - Performance metrics with confidence intervals
   - Fold-by-fold details
   - Final verdict and recommendations

3. **Summary** (`walk_forward_5year_summary_YYYYMMDD_HHMMSS.json`)
   - Quick summary of key metrics
   - Pass/fail status
   - Execution time

## Report Sections

### 1. Configuration
- Date range and symbols
- Train/test window sizes
- Total number of folds

### 2. Out-of-Sample Performance
- **Sharpe Ratio**: Mean, std dev, 95% confidence interval
- **Return**: Mean per quarter with confidence intervals
- **Drawdown**: Mean and worst-case
- **Win Rate**: Consistency metrics

### 3. Robustness Analysis
- **Sharpe Consistency**: % of quarters with positive Sharpe
- **Return Consistency**: % of profitable quarters

### 4. Overfitting Detection
- **Overfitting Score**: 0-1 scale (0=none, 1=severe)
- **Sharpe Decay**: In-sample vs out-of-sample degradation
- **Interpretation**:
  - < 0.3: Low overfitting ✅
  - 0.3-0.6: Moderate overfitting ⚠️
  - > 0.6: High overfitting ❌

### 5. Market Regime Breakdown
Performance across different market conditions:
- Bull markets (low/high volatility)
- Bear markets (low/high volatility)
- Sideways markets

### 6. Validation Status
Pass/fail results against thresholds:
- Minimum OOS Sharpe: 0.8
- Maximum Sharpe Decay: 0.5
- Maximum Drawdown: 15%
- Minimum Win Rate: 52%

### 7. Fold-by-Fold Details
Complete table of all test periods with:
- OOS Sharpe, return, drawdown
- Market regime classification

### 8. Final Verdict
Clear recommendation:
- ✅ **PASSED**: Ready for deployment
- ❌ **FAILED**: Needs improvement with specific recommendations

## Validation Criteria

A strategy passes validation if ALL criteria are met:

| Metric | Threshold | Why It Matters |
|--------|-----------|----------------|
| Mean OOS Sharpe | ≥ 0.8 | Risk-adjusted returns must be positive |
| Sharpe Decay | ≤ 0.5 | Limited overfitting to training data |
| Mean Drawdown | ≤ 15% | Acceptable risk exposure |
| Win Rate | ≥ 52% | More winners than losers |
| Sharpe Consistency | ≥ 60% | Profitable in most periods |

## Interpretation Guide

### Good Signs ✅
- Mean OOS Sharpe > 1.0
- Sharpe consistency > 70%
- Overfitting score < 0.3
- Positive performance across all regimes
- Tight confidence intervals

### Warning Signs ⚠️
- Mean OOS Sharpe 0.5-0.8
- Sharpe consistency 50-60%
- Overfitting score 0.3-0.5
- Large Sharpe decay (IS >> OOS)
- Wide confidence intervals

### Red Flags ❌
- Mean OOS Sharpe < 0.5
- Sharpe consistency < 50%
- Overfitting score > 0.5
- Negative performance in multiple regimes
- Very wide confidence intervals

## Example Output

```
5-YEAR WALK-FORWARD VALIDATION REPORT
Out-of-Sample Performance Analysis (The Truth)

📅 Validation Date: 2024-12-09
⏱️  Execution Time: 32.5 minutes
📊 Strategy: CoreStrategy
💹 Symbols: SPY, QQQ, IWM, VOO, VTI

VALIDATION CONFIGURATION
   Train Window: 252 trading days (~1 year)
   Test Window: 63 trading days (~1 quarter)
   Total Folds: 16

📈 OUT-OF-SAMPLE PERFORMANCE
   Sharpe Ratio:
     Mean: 1.25
     Std Dev: ±0.35
     95% CI: [1.05, 1.45]

   Return per Quarter:
     Mean: 3.8%
     95% CI: [2.5%, 5.1%]

🛡️  ROBUSTNESS ANALYSIS
   Positive Sharpe: 87.5% (14/16 quarters)
   Positive Return: 81.2% (13/16 quarters)

🔍 OVERFITTING DETECTION
   Overfitting Score: 0.23 / 1.0
   ✅ LOW overfitting - strategy generalizes well

🎯 FINAL VERDICT: YES - Strategy has real edge
   💡 RECOMMENDATION: Ready for live deployment
```

## Common Issues

### Issue: "No data returned"
**Solution**: Check symbol names and date range. Some symbols may not have full history.

### Issue: "Insufficient data"
**Solution**: Need at least ~1.5 years of data for minimum validation. Use longer date range.

### Issue: "All windows failed"
**Solution**: Check strategy implementation and data quality. Review logs for specific errors.

### Issue: Script takes too long
**Solution**: Use `--quick` mode for faster testing, or reduce date range.

## Advanced Usage

### Custom Strategy Validation

To validate a different strategy, modify the script:

```python
from src.strategies.your_strategy import YourStrategy

results = validator.run_matrix_evaluation(
    strategy_class=YourStrategy,
    strategy_params={"param1": value1, "param2": value2},
    ...
)
```

### Parallel Validation

For multiple strategies or parameter sets, use the underlying API:

```python
from src.backtesting.walk_forward_matrix import WalkForwardMatrixValidator

validator = WalkForwardMatrixValidator(
    train_window_days=252,
    test_window_days=63,
    step_days=63,
)

# Run for multiple parameter sets
for params in param_grid:
    results = validator.run_matrix_evaluation(...)
```

## Integration with CI/CD

Add to your CI pipeline:

```yaml
# .github/workflows/validation.yml
- name: Run 5-year validation
  run: |
    python scripts/run_5year_validation.py --quick
    if [ $? -ne 0 ]; then
      echo "Strategy validation failed!"
      exit 1
    fi
```

## Best Practices

1. **Always validate before deploying**: Never skip walk-forward validation
2. **Use full 5-year period**: Includes multiple market regimes
3. **Check all metrics**: Don't just look at Sharpe ratio
4. **Review fold-by-fold**: Identify which periods fail
5. **Monitor overfitting score**: Should be < 0.3 for production
6. **Compare across strategies**: Use consistent validation for all strategies
7. **Revalidate periodically**: Market conditions change, revalidate quarterly

## Next Steps

After validation:

1. **If PASSED**:
   - Start with small position sizes (10% of planned)
   - Monitor live vs backtest divergence
   - Scale up gradually over 3 months
   - Revalidate after 6 months

2. **If FAILED**:
   - Review specific failure reasons
   - Focus on worst-performing regimes
   - Simplify strategy if overfitting score high
   - Improve risk management if drawdown too high
   - Revalidate after improvements

## References

- [Walk-Forward Analysis](https://en.wikipedia.org/wiki/Walk_forward_optimization)
- [Overfitting in Trading](https://www.quantstart.com/articles/Backtesting-An-Algorithmic-Trading-Strategy/)
- Existing implementations:
  - `/home/user/trading/src/backtesting/walk_forward.py`
  - `/home/user/trading/src/backtesting/walk_forward_enhanced.py`
  - `/home/user/trading/src/backtesting/walk_forward_matrix.py`

---

**Last Updated**: 2024-12-09
**Script Location**: `/home/user/trading/scripts/run_5year_validation.py`
