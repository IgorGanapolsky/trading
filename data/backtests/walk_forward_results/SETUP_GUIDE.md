# Walk-Forward Validation Setup Guide

**Purpose**: Complete guide to set up environment and run proper 3+ year walk-forward validation.

---

## Prerequisites

### 1. Python Environment
```bash
# Create isolated virtual environment
cd /home/user/trading
python3 -m venv venv
source venv/bin/activate

# Verify Python version (need 3.9+)
python --version
```

### 2. Install Dependencies
```bash
# Core dependencies
pip install --upgrade pip setuptools wheel

# Data science stack
pip install numpy==1.24.3
pip install pandas==2.0.3
pip install scipy==1.11.1

# Financial data
pip install yfinance==0.2.28
pip install alpaca-py==0.15.0

# Machine learning (optional for ML models)
pip install torch==2.0.1
pip install scikit-learn==1.3.0

# Verification
python -c "import numpy, pandas, scipy, yfinance; print('✅ All packages installed')"
```

### 3. API Credentials (Optional but Recommended)

**Option A: Yahoo Finance (Free, No API Key)**
- Works out of the box with yfinance
- Rate limited but sufficient for backtesting
- No setup required

**Option B: Alpaca (Free Paper Trading Account)**
```bash
# Get API keys from alpaca.markets
# Add to .env file:
ALPACA_API_KEY=your_key_here
ALPACA_API_SECRET=your_secret_here
ALPACA_PAPER=true
```

---

## Data Collection

### Fetch 3+ Years of Historical Data

**Method 1: Using yfinance (Recommended for Initial Testing)**

```python
import yfinance as yf
import pandas as pd
from pathlib import Path

# Create directory
Path("data/historical/multi_year").mkdir(parents=True, exist_ok=True)

# Fetch 3+ years for primary ETFs
symbols = ["SPY", "QQQ", "VOO", "BND"]
start_date = "2022-01-01"
end_date = "2025-12-04"

for symbol in symbols:
    print(f"Fetching {symbol}...")
    ticker = yf.Ticker(symbol)
    df = ticker.history(start=start_date, end=end_date, interval="1d")

    # Save to CSV
    output_path = f"data/historical/multi_year/{symbol}_{start_date}_{end_date}.csv"
    df.to_csv(output_path)
    print(f"  ✅ Saved {len(df)} days to {output_path}")

print(f"\n✅ Data collection complete!")
print(f"   Period: {start_date} to {end_date}")
print(f"   Symbols: {', '.join(symbols)}")
print(f"   Expected days: ~756 trading days")
```

**Method 2: Using Alpaca API**

```python
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime
import os

# Initialize client
client = StockHistoricalDataClient(
    api_key=os.getenv("ALPACA_API_KEY"),
    secret_key=os.getenv("ALPACA_API_SECRET"),
)

# Fetch data
symbols = ["SPY", "QQQ", "VOO"]
request = StockBarsRequest(
    symbol_or_symbols=symbols,
    timeframe=TimeFrame.Day,
    start=datetime(2022, 1, 1),
    end=datetime(2025, 12, 4),
)

bars = client.get_stock_bars(request)
# Process and save...
```

### Verify Data Quality

```python
import pandas as pd
from pathlib import Path

data_dir = Path("data/historical/multi_year")
required_days = 700  # Minimum for 3 years

for file in data_dir.glob("*.csv"):
    df = pd.read_csv(file, index_col=0, parse_dates=True)
    symbol = file.stem.split("_")[0]

    print(f"\n{symbol}:")
    print(f"  Days: {len(df)}")
    print(f"  Period: {df.index[0].date()} to {df.index[-1].date()}")
    print(f"  Columns: {', '.join(df.columns)}")

    if len(df) < required_days:
        print(f"  ⚠️  WARNING: Only {len(df)} days (need {required_days}+)")
    else:
        print(f"  ✅ PASS: {len(df)} days")

    # Check for missing data
    missing = df.isnull().sum().sum()
    if missing > 0:
        print(f"  ⚠️  WARNING: {missing} missing values")
    else:
        print(f"  ✅ No missing data")
```

---

## Running Walk-Forward Validation

### Step 1: Configuration Check

```bash
# Verify environment
python -c "import sys; print(f'Python: {sys.version}')"
python -c "import numpy, pandas, scipy, yfinance; print('✅ Dependencies OK')"

# Verify data exists
ls -lh data/historical/multi_year/

# Verify walk-forward script exists
ls -lh scripts/run_walk_forward_validation.py
```

### Step 2: Run Validation

```bash
# Full 3+ year walk-forward validation
python scripts/run_walk_forward_validation.py

# Expected output:
#   - 10-12 walk-forward folds
#   - ~5-10 minutes runtime
#   - Results saved to data/backtests/walk_forward_results/
```

### Step 3: Review Results

```bash
# View comprehensive report
cat data/backtests/walk_forward_results/latest_report.txt

# View JSON results for programmatic analysis
python -c "
import json
with open('data/backtests/walk_forward_results/latest_results.json') as f:
    results = json.load(f)
    print(f'Mean OOS Sharpe: {results[\"mean_oos_sharpe\"]:.2f}')
    print(f'Overfitting Score: {results[\"overfitting_score\"]:.2f}')
    print(f'Passed Validation: {results[\"passed_validation\"]}')
"
```

---

## Interpreting Results

### Key Metrics

**1. Mean Out-of-Sample Sharpe Ratio**
```
>= 1.5: Excellent - deploy with confidence ✅
>= 1.0: Good - acceptable for deployment ✅
>= 0.5: Weak - requires improvement ⚠️
< 0.5: Poor - do NOT deploy ❌
```

**2. Overfitting Score (0-1)**
```
< 0.3: Low overfitting - strategy generalizes well ✅
0.3-0.6: Moderate - review parameters ⚠️
> 0.6: High overfitting - likely curve-fit ❌
```

**3. Sharpe Consistency**
```
>= 70%: Most test periods profitable ✅
>= 60%: Acceptable consistency ✅
>= 50%: Inconsistent - caution ⚠️
< 50%: Poor consistency - do NOT deploy ❌
```

**4. Mean Out-of-Sample Max Drawdown**
```
< 10%: Excellent risk management ✅
< 15%: Acceptable ✅
< 20%: High risk - review ⚠️
>= 20%: Unacceptable - do NOT deploy ❌
```

### 95% Confidence Intervals

**What They Mean**:
- Sharpe CI: [1.2, 1.8] → True Sharpe is 95% likely between 1.2-1.8
- Return CI: [8%, 15%] → True annual return is 95% likely between 8-15%

**When to Trust Results**:
- ✅ Narrow CI (width < 0.5 Sharpe) → Confident
- ⚠️ Wide CI (width > 1.0 Sharpe) → Need more data

### Regime Performance

**What to Look For**:
- ✅ Positive Sharpe in ALL regimes (bull/bear/sideways)
- ✅ Consistent across high/low volatility
- ❌ Only works in one regime → Overfit

**Example Good Results**:
```
Bull Low Vol:    Sharpe 2.1, Return 18%, Win Rate 65%
Bull High Vol:   Sharpe 1.4, Return 12%, Win Rate 58%
Bear High Vol:   Sharpe 0.8, Return -3%, Win Rate 52%  ← Still positive!
Sideways:        Sharpe 1.2, Return 7%, Win Rate 55%
```

**Example Bad Results** (Overfit):
```
Bull Low Vol:    Sharpe 3.5, Return 28%, Win Rate 72%  ← Suspiciously high
Bull High Vol:   Sharpe 0.2, Return 1%, Win Rate 48%   ← Barely works
Bear High Vol:   Sharpe -1.2, Return -15%, Win Rate 35%  ← Fails in bear!
Sideways:        Sharpe -0.3, Return -2%, Win Rate 47%  ← Also fails
```

---

## Decision Framework

### Go/No-Go Criteria

**Deploy Strategy if ALL of the following are true**:
- ✅ Mean OOS Sharpe >= 1.0
- ✅ Overfitting Score < 0.3
- ✅ Sharpe Consistency >= 60%
- ✅ Mean OOS Max Drawdown < 15%
- ✅ 95% CI for Sharpe excludes 0
- ✅ Positive Sharpe in at least 3/4 regimes

**Do NOT Deploy if ANY of the following are true**:
- ❌ Mean OOS Sharpe < 0.5
- ❌ Overfitting Score > 0.6
- ❌ Sharpe Consistency < 50%
- ❌ Mean OOS Max Drawdown > 20%
- ❌ 95% CI for Sharpe includes 0
- ❌ Negative Sharpe in bear markets (means will lose in downturns)

### Example Decisions

**Scenario A: Strong Strategy**
```
Mean OOS Sharpe: 1.4 (95% CI: [1.1, 1.7])
Overfitting: 0.2
Consistency: 75%
Max DD: 12%

Decision: ✅ DEPLOY - meets all criteria
```

**Scenario B: Weak Strategy**
```
Mean OOS Sharpe: 0.6 (95% CI: [0.1, 1.1])
Overfitting: 0.5
Consistency: 55%
Max DD: 18%

Decision: ⚠️ CAUTION - marginal, needs improvement
```

**Scenario C: Overfit Strategy**
```
Mean OOS Sharpe: 0.3 (95% CI: [-0.2, 0.8])
Overfitting: 0.8
Consistency: 45%
Max DD: 25%

Decision: ❌ DO NOT DEPLOY - likely curve-fit
```

---

## Troubleshooting

### Issue: "No module named 'numpy'"
```bash
# Activate virtual environment
source venv/bin/activate

# Verify you're in venv
which python  # Should show /home/user/trading/venv/bin/python

# Reinstall dependencies
pip install numpy pandas scipy yfinance
```

### Issue: "Insufficient data for validation folds"
```bash
# Check data files
ls -lh data/historical/multi_year/

# Verify data length
python -c "
import pandas as pd
df = pd.read_csv('data/historical/multi_year/SPY_2022-01-01_2025-12-04.csv')
print(f'Days: {len(df)} (need 700+)')
"

# If < 700 days, re-fetch with longer date range
```

### Issue: "yfinance download failed"
```bash
# Try again (sometimes Yahoo rate-limits)
sleep 60
python fetch_historical_data.py

# Or use Alpaca API instead
# (see Method 2 above)
```

### Issue: "Walk-forward validation takes too long"
```python
# Reduce fold count for faster testing
# In run_walk_forward_validation.py, change:
validator = WalkForwardMatrixValidator(
    train_window_days=252,  # Keep
    test_window_days=63,    # Keep
    step_days=63,           # Change from 21 → 63 (faster, fewer folds)
)
```

---

## FAQ

**Q: How long does walk-forward validation take?**
A: 5-10 minutes for 10 folds. Longer if fetching data for the first time.

**Q: Can I use this for other strategies?**
A: Yes! Just change `strategy_class` in the script:
```python
from src.strategies.your_strategy import YourStrategy
results = validator.run_matrix_evaluation(
    strategy_class=YourStrategy,
    ...
)
```

**Q: What if my strategy fails validation?**
A: Options:
1. Adjust parameters (but watch for overfitting!)
2. Try different indicators
3. Add regime filters
4. Redesign strategy entirely
5. Accept that strategy doesn't have robust edge

**Q: Can I trust a Sharpe ratio from 252 days?**
A: 252 days (1 year) is minimum for basic confidence. 756 days (3 years) is better. 1260 days (5 years) is ideal.

**Q: What about transaction costs?**
A: Walk-forward validator includes slippage model by default (5 bps base + market impact). Results account for realistic execution costs.

**Q: What if I don't have 3 years of data?**
A: Use whatever you have, but increase the train/test window sizes proportionally:
- 2 years: 180 day train, 45 day test
- 1 year: 90 day train, 22 day test
- < 1 year: Results not reliable

---

## Next Steps After Validation

### If Strategy Passes ✅

1. **Start Paper Trading**
   - Deploy to Alpaca paper account
   - Run for 30+ days
   - Track live vs backtest divergence

2. **Monitor Live Performance**
   - Daily Sharpe ratio calculation
   - Drawdown tracking
   - Win rate validation

3. **Go-Live Decision (After 30 Days)**
   - Live Sharpe within 0.5 of backtest? ✅ Go live
   - Live Sharpe < backtest - 1.0? ⚠️ Wait longer
   - Live Sharpe < 0? ❌ Back to drawing board

### If Strategy Fails ❌

1. **Analyze Failure Modes**
   - Which regimes failed?
   - Where did overfitting occur?
   - What parameters were unstable?

2. **Redesign Strategy**
   - Add regime filters
   - Simplify parameters
   - Use more robust indicators
   - Consider ensemble approaches

3. **Re-run Validation**
   - Test new strategy on same data
   - Compare overfitting scores
   - Validate improvements

---

## Resources

**Walk-Forward Validation Code**:
- `src/backtesting/walk_forward_matrix.py` - Main validator
- `src/backtesting/walk_forward.py` - Base utilities
- `scripts/run_walk_forward_validation.py` - Runner script

**Documentation**:
- `data/backtests/walk_forward_results/HONEST_ASSESSMENT.md` - Current state
- `docs/backtesting.md` - Backtest engine docs (if exists)

**External References**:
- [Walk-Forward Analysis (Investopedia)](https://www.investopedia.com/terms/w/walk-forward-analysis.asp)
- [Avoiding Overfitting in Trading](https://quantitativo.com/avoiding-overfitting/)
- [Sharpe Ratio Confidence Intervals](https://www.investopedia.com/articles/07/sharpe_ratio.asp)

---

**Document Version**: 1.0
**Last Updated**: 2025-12-04
**Status**: Ready for Implementation
