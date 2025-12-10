# 5-Year Walk-Forward Validation

## Quick Start

```bash
# 1. Check dependencies
python scripts/check_validation_deps.py

# 2. Run validation (will take 30-45 minutes)
python scripts/run_5year_validation.py

# 3. Check results
ls -lh reports/walk_forward_5year_*
```

## What This Does

Runs comprehensive 5-year rolling walk-forward validation to determine if your trading strategy has a real edge on unseen out-of-sample data. This is the gold standard test before deploying real capital.

## Why This Matters

**Without walk-forward validation:**
- You don't know if your strategy is curve-fit to historical data
- High risk of deploying a strategy that fails in live trading
- No confidence in expected performance

**With walk-forward validation:**
- Know true out-of-sample performance
- Detect overfitting before deployment
- Understand performance across different market regimes
- Deploy with confidence

## How It Works

```
2019-2024 Data (5 years)
│
├─ Window 1: Train(2019) → Test(Q1 2020)
├─ Window 2: Train(2019-Q1 2020) → Test(Q2 2020)
├─ Window 3: Train(2019-Q2 2020) → Test(Q3 2020)
├─ ...
└─ Window 16: Train(2019-2023) → Test(Q4 2024)

Result: 16 independent out-of-sample tests
```

Each window:
1. Trains on past data (1 year)
2. Tests on unseen future data (1 quarter)
3. No look-ahead bias (training always before testing)
4. Independent performance measurement

## Files

| File | Purpose |
|------|---------|
| `run_5year_validation.py` | Main validation script |
| `check_validation_deps.py` | Dependency checker |
| `../docs/5year_validation_guide.md` | Complete usage guide |
| `../docs/5year_validation_sample_output.md` | Example outputs |

## Prerequisites

### Required Python Packages

```bash
pip install -r requirements.txt
```

Key dependencies:
- `numpy` - Numerical computing
- `pandas` - Data manipulation
- `yfinance` - Market data fetching
- `scipy` - Statistical functions

### Required Project Modules

Ensure these exist in your `src/` directory:
- `src/backtesting/walk_forward_matrix.py` - ✅ Exists
- `src/strategies/core_strategy.py` - ✅ Exists

To verify: `python scripts/check_validation_deps.py`

## Usage Examples

### Basic - Default 5 years

```bash
python scripts/run_5year_validation.py
```

Validates using:
- Period: 2019-01-01 to 2024-12-31
- Symbols: SPY, QQQ, IWM, VOO, VTI
- Initial capital: $100,000
- Daily allocation: $10

### Custom Date Range

```bash
python scripts/run_5year_validation.py \
  --start 2018-01-01 \
  --end 2023-12-31
```

### Custom Symbols

```bash
python scripts/run_5year_validation.py \
  --symbols SPY QQQ DIA VTI
```

### Custom Parameters

```bash
python scripts/run_5year_validation.py \
  --daily-allocation 15.0 \
  --initial-capital 50000.0 \
  --output-dir validation_results
```

### Quick Test (Faster)

```bash
python scripts/run_5year_validation.py --quick
```

Uses larger step size (126 days) for faster execution. Good for quick checks, but use full validation for production deployment.

## Output

The script generates three files in `reports/`:

### 1. JSON Results (`walk_forward_5year_YYYYMMDD_HHMMSS.json`)

Complete validation data:
```json
{
  "strategy_name": "CoreStrategy",
  "mean_oos_sharpe": 1.25,
  "sharpe_consistency": 0.875,
  "overfitting_score": 0.230,
  "passed_validation": true,
  "windows": [...]
}
```

### 2. Text Report (`walk_forward_5year_YYYYMMDD_HHMMSS.txt`)

Human-readable comprehensive report with:
- Configuration summary
- Out-of-sample performance metrics
- Confidence intervals
- Overfitting analysis
- Regime breakdown
- Fold-by-fold details
- Final verdict and recommendations

### 3. Summary (`walk_forward_5year_summary_YYYYMMDD_HHMMSS.json`)

Quick summary for dashboards:
```json
{
  "mean_oos_sharpe": 1.25,
  "passed_validation": true,
  "execution_time_minutes": 32.5
}
```

## Interpreting Results

### Key Metrics

| Metric | Good | Marginal | Poor |
|--------|------|----------|------|
| Mean OOS Sharpe | > 1.0 | 0.5-1.0 | < 0.5 |
| Sharpe Consistency | > 70% | 55-70% | < 55% |
| Overfitting Score | < 0.3 | 0.3-0.5 | > 0.5 |
| Win Rate | > 55% | 50-55% | < 50% |

### Pass/Fail Criteria

Strategy PASSES if ALL conditions met:
- ✅ Mean OOS Sharpe ≥ 0.8
- ✅ Sharpe Decay ≤ 0.5 (limited overfitting)
- ✅ Mean Drawdown ≤ 15%
- ✅ Win Rate ≥ 52%
- ✅ Consistency ≥ 60%

### What Each Metric Means

**Sharpe Ratio**: Risk-adjusted returns
- Higher = better (>1.0 is good, >1.5 is excellent)
- Accounts for volatility

**Sharpe Consistency**: % of quarters profitable
- 87.5% = 14 out of 16 quarters had positive Sharpe
- Higher = more reliable

**Overfitting Score**: 0-1 scale
- 0.0 = No overfitting (IS = OOS)
- 1.0 = Severe overfitting (IS >> OOS)
- < 0.3 is acceptable for production

**Sharpe Decay**: In-sample minus out-of-sample Sharpe
- Lower = better generalization
- High decay = strategy overfit to training data

## Common Issues

### "No module named 'numpy'"

**Solution**: Install dependencies
```bash
pip install -r requirements.txt
```

### "No data returned for symbol"

**Solution**: Check symbol validity and date range
```bash
# Test data download manually
python -c "import yfinance as yf; print(yf.Ticker('SPY').history(start='2019-01-01', end='2024-12-31'))"
```

### "Insufficient data" error

**Solution**: Need minimum ~1.5 years of data
```bash
# Use longer date range
python scripts/run_5year_validation.py --start 2019-01-01 --end 2024-12-31
```

### Script takes too long

**Solutions**:
1. Use `--quick` flag for faster testing
2. Reduce date range
3. Test on fewer symbols first
4. Run overnight for full validation

### "All windows failed evaluation"

**Solutions**:
1. Check strategy implementation
2. Verify data quality
3. Review error logs for specific issues
4. Test strategy on single period first

## Performance

**Typical execution times:**
- Quick mode (`--quick`): ~15-20 minutes
- Full validation: ~30-45 minutes
- Depends on:
  - Number of symbols
  - Date range
  - Network speed (data download)
  - CPU speed (backtesting)

**Progress tracking:**
- Console shows current fold being processed
- Estimated remaining time provided
- Can be safely interrupted (Ctrl+C)

## Best Practices

1. **Always validate before deploying**
   - Never skip this step
   - One validation is not enough (market conditions change)

2. **Use full 5-year period**
   - Includes COVID crash, recovery, bull markets
   - Tests multiple regimes

3. **Don't cherry-pick dates**
   - Use consistent date ranges
   - Include bear markets

4. **Revalidate regularly**
   - Every 6 months minimum
   - After major strategy changes
   - After significant market regime changes

5. **Compare multiple strategies**
   - Use same validation period
   - Same metrics for fair comparison

6. **Monitor overfitting score**
   - Target < 0.25 for production
   - If > 0.35, simplify strategy

## Next Steps

### If Validation PASSED ✅

1. **Start conservative**:
   ```bash
   # Begin with 10% of planned capital
   initial_capital_10pct = planned_capital * 0.1
   ```

2. **Monitor live performance**:
   - Track live vs backtest divergence
   - Watch for regime changes
   - Adjust position sizes if needed

3. **Scale gradually**:
   - Week 1-4: 10% capital
   - Week 5-8: 25% capital
   - Week 9-12: 50% capital
   - Month 4+: Full capital (if performing well)

4. **Revalidate in 6 months**:
   ```bash
   python scripts/run_5year_validation.py --start 2019-07-01
   ```

### If Validation FAILED ❌

1. **Identify root cause**:
   - Check overfitting score
   - Review regime breakdown
   - Analyze failed windows

2. **Common fixes**:

   **High overfitting (score > 0.5)**:
   ```python
   # Simplify model
   # - Reduce number of parameters
   # - Add regularization
   # - Use simpler indicators
   ```

   **Low Sharpe (< 0.5)**:
   ```python
   # Improve signals
   # - Better entry/exit logic
   # - Enhanced feature engineering
   # - Stronger filters
   ```

   **High drawdown (> 15%)**:
   ```python
   # Better risk management
   # - Tighter stop losses
   # - Position sizing rules
   # - Portfolio diversification
   ```

   **Regime-specific failures**:
   ```python
   # Add regime awareness
   # - Adjust position sizes by regime
   # - Different parameters per regime
   # - Skip trading in bad regimes
   ```

3. **Revalidate after changes**:
   ```bash
   python scripts/run_5year_validation.py
   ```

4. **Document results**:
   - Track what worked/didn't work
   - Build intuition for your strategy
   - Learn from failures

## Integration with CI/CD

Add to GitHub Actions:

```yaml
# .github/workflows/validation.yml
name: Strategy Validation

on:
  pull_request:
    paths:
      - 'src/strategies/**'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Check validation dependencies
        run: python scripts/check_validation_deps.py

      - name: Run quick validation
        run: python scripts/run_5year_validation.py --quick

      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: validation-results
          path: reports/walk_forward_5year_*
```

## Related Documentation

- **Complete Guide**: `../docs/5year_validation_guide.md`
- **Sample Output**: `../docs/5year_validation_sample_output.md`
- **Walk-Forward Base**: `../src/backtesting/walk_forward.py`
- **Enhanced Validation**: `../src/backtesting/walk_forward_enhanced.py`
- **Matrix Validator**: `../src/backtesting/walk_forward_matrix.py`

## Support

For issues or questions:
1. Check logs in console output
2. Review documentation in `docs/`
3. Verify dependencies with `check_validation_deps.py`
4. Test on small date range first

## References

- [Walk-Forward Analysis](https://en.wikipedia.org/wiki/Walk_forward_optimization)
- [Overfitting in Trading Systems](https://www.quantstart.com/articles/Backtesting-An-Algorithmic-Trading-Strategy/)
- [Proper Backtesting Methodology](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2308659)

---

**Script**: `/home/user/trading/scripts/run_5year_validation.py`
**Created**: 2024-12-09
**Author**: Trading System
