# Options Backtesting Engine - World-Class Implementation

**Created**: December 10, 2025
**Location**: `src/backtesting/options_backtest.py`
**Author**: Trading System

---

## Overview

Professional-grade options backtesting engine with full Black-Scholes pricing, Greeks tracking, and comprehensive performance analytics. Designed for institutional-quality strategy validation.

## Features

### Core Capabilities

1. **Black-Scholes Pricing Engine**
   - Full European options pricing
   - All Greeks calculation (Delta, Gamma, Theta, Vega, Rho)
   - Historical IV estimation from HV
   - Dividend yield support

2. **Multi-Strategy Support**
   - Covered Calls
   - Iron Condors
   - Credit Spreads (Put/Call)
   - Debit Spreads
   - Straddles/Strangles
   - Calendar Spreads
   - Cash-Secured Puts
   - Vertical Spreads

3. **Position Management**
   - Multi-leg position tracking
   - Entry/exit price tracking
   - Commission modeling ($0.65/contract)
   - Assignment/exercise simulation
   - P/L calculation with Greeks

4. **Performance Metrics**
   - Standard metrics: Sharpe, Sortino, Calmar ratios
   - Drawdown analysis (max, average, rolling)
   - Win rate, profit factor
   - Options-specific: Days in trade, theta income
   - Greeks exposure tracking
   - Strategy-level breakdown

5. **Report Generation**
   - Text reports with comprehensive metrics
   - Equity curve charts (matplotlib)
   - Drawdown visualization
   - Trade-by-trade logs
   - JSON export for analysis

---

## Architecture

```
OptionsBacktestEngine
├── BlackScholesPricer       # Options pricing & Greeks
├── OptionsPosition          # Multi-leg position tracking
│   └── OptionsLeg          # Individual option leg
├── BacktestMetrics         # Comprehensive performance metrics
└── Report Generator        # Charts & analysis output
```

### Key Classes

#### `OptionsBacktestEngine`
Main orchestrator for backtesting strategies.

```python
engine = OptionsBacktestEngine(
    start_date="2024-01-01",
    end_date="2024-12-31",
    initial_capital=100000.0,
    risk_free_rate=0.04,
    commission_per_contract=0.65,
)
```

#### `OptionsPosition`
Complete multi-leg position with P/L tracking.

```python
position = OptionsPosition(
    symbol="SPY",
    strategy=StrategyType.COVERED_CALL,
    legs=[leg1, leg2, ...],
    entry_date=datetime(2024, 1, 15),
    entry_price=450.0,
)
```

#### `OptionsLeg`
Individual option component.

```python
leg = OptionsLeg(
    option_type=OptionType.CALL,
    strike=105.0,
    expiration=datetime(2024, 2, 15),
    quantity=-1,  # Short
    entry_premium=2.50,
    delta=0.30,
    theta=-0.05,
    vega=0.15,
)
```

#### `BlackScholesPricer`
Full Black-Scholes implementation with Greeks.

```python
pricer = BlackScholesPricer()
result = pricer.calculate(
    spot=100.0,
    strike=105.0,
    time_to_expiry=0.25,  # years
    risk_free_rate=0.04,
    volatility=0.20,
    option_type=OptionType.CALL,
)
# Returns: {price, delta, gamma, theta, vega, rho}
```

---

## Usage Examples

### Example 1: Covered Call Strategy

```python
from datetime import datetime, timedelta
from src.backtesting.options_backtest import (
    OptionsBacktestEngine,
    OptionsPosition,
    OptionsLeg,
    OptionType,
    StrategyType,
    BlackScholesPricer,
)

def covered_call_strategy(symbol, date, hist):
    """Sell 30-delta calls 35 DTE."""
    current_price = float(hist['Close'].iloc[-1])
    iv = float(hist['IV_Est'].iloc[-1])

    pricer = BlackScholesPricer()
    strike = current_price * 1.05  # 5% OTM

    result = pricer.calculate(
        spot=current_price,
        strike=strike,
        time_to_expiry=35/365,
        risk_free_rate=0.04,
        volatility=iv,
        option_type=OptionType.CALL,
    )

    leg = OptionsLeg(
        option_type=OptionType.CALL,
        strike=strike,
        expiration=date + timedelta(days=35),
        quantity=-1,
        entry_premium=result['price'],
        delta=result['delta'],
        theta=result['theta'],
        vega=result['vega'],
        iv=iv,
    )

    position = OptionsPosition(
        symbol=symbol,
        strategy=StrategyType.COVERED_CALL,
        legs=[leg],
        entry_date=date,
        entry_price=current_price,
    )

    position.calculate_entry_cost()
    return position

# Run backtest
engine = OptionsBacktestEngine(
    start_date="2024-01-01",
    end_date="2024-12-31",
    initial_capital=100000,
)

metrics = engine.run_backtest(
    strategy=covered_call_strategy,
    symbols=["SPY", "QQQ"],
    trade_frequency_days=7,
)

# Generate report
report_path = engine.generate_report(metrics)
print(f"Report saved: {report_path}")
```

### Example 2: Iron Condor Strategy

```python
def iron_condor_strategy(symbol, date, hist):
    """Sell 16-delta wings, 45 DTE."""
    current_price = float(hist['Close'].iloc[-1])
    iv = float(hist['IV_Est'].iloc[-1])

    pricer = BlackScholesPricer()
    expiration = date + timedelta(days=45)

    # Build 4-leg iron condor
    legs = [
        # Put spread
        OptionsLeg(
            option_type=OptionType.PUT,
            strike=current_price * 0.94,  # Short put
            expiration=expiration,
            quantity=-1,
            entry_premium=2.00,
            delta=-0.16,
        ),
        OptionsLeg(
            option_type=OptionType.PUT,
            strike=current_price * 0.89,  # Long put
            expiration=expiration,
            quantity=1,
            entry_premium=0.80,
            delta=-0.05,
        ),
        # Call spread
        OptionsLeg(
            option_type=OptionType.CALL,
            strike=current_price * 1.06,  # Short call
            expiration=expiration,
            quantity=-1,
            entry_premium=2.00,
            delta=0.16,
        ),
        OptionsLeg(
            option_type=OptionType.CALL,
            strike=current_price * 1.11,  # Long call
            expiration=expiration,
            quantity=1,
            entry_premium=0.80,
            delta=0.05,
        ),
    ]

    position = OptionsPosition(
        symbol=symbol,
        strategy=StrategyType.IRON_CONDOR,
        legs=legs,
        entry_date=date,
        entry_price=current_price,
    )

    position.calculate_entry_cost()
    return position
```

### Example 3: Using the Sample Script

```bash
# Run all strategies
python scripts/run_options_backtest.py --strategy all --save

# Run specific strategy
python scripts/run_options_backtest.py \
    --strategy covered_call \
    --start 2024-01-01 \
    --end 2024-12-31 \
    --symbols SPY QQQ IWM \
    --capital 50000 \
    --save

# Compare strategies
python scripts/run_options_backtest.py --strategy all
```

---

## Performance Metrics

### Standard Metrics
- **Total Return**: Percentage return on capital
- **CAGR**: Compound Annual Growth Rate
- **Sharpe Ratio**: Risk-adjusted return (annualized)
- **Sortino Ratio**: Downside risk-adjusted return
- **Max Drawdown**: Largest peak-to-trough decline
- **Calmar Ratio**: CAGR / Max Drawdown

### Trade Statistics
- **Total Trades**: Number of completed positions
- **Win Rate**: Percentage of profitable trades
- **Profit Factor**: Gross wins / Gross losses
- **Average Win/Loss**: Mean P/L per trade
- **Largest Win/Loss**: Best/worst single trade

### Options-Specific Metrics
- **Avg Days in Trade**: Average holding period
- **Total Commissions**: Cumulative transaction costs
- **Avg Delta Exposure**: Portfolio delta sensitivity
- **Avg Theta Income**: Daily time decay profit
- **Avg Vega Exposure**: IV risk exposure

### Strategy Breakdown
Per-strategy performance:
- Trades executed
- Win rate
- Total P/L
- Average P/L per trade

---

## Configuration

### Position Sizing
Controlled via strategy implementation. Common approaches:
- Fixed dollar amount per trade
- Percentage of portfolio
- Kelly Criterion
- Volatility-adjusted sizing

### Commission Model
Default: $0.65 per contract (Alpaca rates)
Adjustable via engine initialization:

```python
engine = OptionsBacktestEngine(
    commission_per_contract=1.00,  # Higher commission
)
```

### Risk Management
Implement in strategy function:
- Maximum position size limits
- Stop-loss / take-profit rules
- Portfolio heat limits
- Correlation constraints

---

## Report Output

### Text Report Format
```
================================================================================
OPTIONS BACKTEST REPORT
================================================================================

Period: 2024-01-01 to 2024-12-31
Trading Days: 252

================================================================================
RETURNS
================================================================================
Total Return: +15.50%
CAGR: +15.23%
Avg Daily Return: +0.06%

================================================================================
RISK METRICS
================================================================================
Sharpe Ratio: 1.85
Sortino Ratio: 2.10
Max Drawdown: 8.50%
Avg Drawdown: 2.30%
Calmar Ratio: 1.79

================================================================================
TRADE STATISTICS
================================================================================
Total Trades: 48
Winning Trades: 36
Losing Trades: 12
Win Rate: 75.0%
Profit Factor: 2.50
...
```

### Chart Output
- Equity curve (line chart)
- Drawdown chart (area chart)
- Saved as PNG (300 DPI)

---

## Testing

Comprehensive test suite at `tests/test_options_backtest.py`:

### Test Coverage
1. **Black-Scholes Pricer**
   - ATM/OTM pricing accuracy
   - Put-call parity
   - Greeks calculation
   - Expiration intrinsic value

2. **Options Leg & Position**
   - Entry cost calculation
   - Multi-leg construction
   - P/L calculation (win/loss)
   - Commission modeling

3. **Backtest Engine**
   - Data loading
   - Trade simulation
   - Metrics calculation
   - Report generation

4. **Strategy Examples**
   - Covered calls
   - Iron condors
   - Credit spreads
   - Straddles

### Running Tests

```bash
# Run all tests
pytest tests/test_options_backtest.py -v

# Run specific test class
pytest tests/test_options_backtest.py::TestBlackScholesPricer -v

# Run with coverage
pytest tests/test_options_backtest.py --cov=src/backtesting/options_backtest
```

---

## Files Created

1. **`src/backtesting/options_backtest.py`** (35KB)
   - Main engine implementation
   - Black-Scholes pricer
   - Position tracking classes
   - Metrics calculator

2. **`tests/test_options_backtest.py`** (22KB)
   - Comprehensive test suite
   - 50+ test cases
   - Strategy examples

3. **`scripts/run_options_backtest.py`** (21KB)
   - Sample implementation
   - 4 ready-to-use strategies
   - CLI interface
   - Comparison reporting

4. **`docs/options_backtest_engine.md`** (this file)
   - Complete documentation
   - Usage examples
   - API reference

5. **Updated `src/backtesting/__init__.py`**
   - Exposed options backtest classes
   - Module integration

---

## Supported Strategies

### 1. Covered Calls
Sell OTM calls against long stock for income.

**Parameters**:
- Delta: 0.20-0.35
- DTE: 30-45 days
- Strike: 5-10% OTM

### 2. Iron Condors
Sell OTM put spread + OTM call spread for range-bound income.

**Parameters**:
- Short strikes: 0.16 delta
- Long strikes: 0.05 delta
- DTE: 45 days
- Width: 5-10% OTM

### 3. Credit Spreads
Sell OTM vertical spread for defined risk income.

**Parameters**:
- Short strike: 0.20 delta
- Long strike: 0.10 delta
- DTE: 30-45 days
- Width: $5-$10

### 4. Cash-Secured Puts
Sell OTM puts to acquire stock at discount.

**Parameters**:
- Delta: 0.30
- DTE: 30 days
- Strike: 5% OTM

### 5. Straddles/Strangles
Buy ATM/OTM options for volatility plays.

**Parameters**:
- Straddle: Both ATM
- Strangle: 5-10% OTM
- DTE: 30-60 days

### 6. Calendar Spreads
Sell near-term, buy far-term for theta capture.

**Parameters**:
- Near: 30 DTE
- Far: 60-90 DTE
- Strike: ATM or slightly OTM

---

## Best Practices

### Strategy Development
1. **Start Simple**: Test single-leg strategies first
2. **Validate Greeks**: Ensure delta/theta align with expectations
3. **Check P/L Logic**: Manually verify credit/debit calculations
4. **Test Edge Cases**: Expiration, early assignment, extreme moves

### Performance Analysis
1. **Compare Multiple Periods**: Test across bull/bear/sideways markets
2. **Walk-Forward Validation**: Use rolling windows
3. **Monte Carlo**: Simulate parameter uncertainty
4. **Benchmark**: Compare to buy-and-hold, other strategies

### Risk Management
1. **Position Limits**: Cap allocation per trade
2. **Portfolio Heat**: Total risk exposure limits
3. **Stop-Loss**: Define exit rules for losers
4. **Take-Profit**: Lock in winners at targets

---

## Limitations & Future Enhancements

### Current Limitations
1. **European Options Only**: No early exercise modeling
2. **Single Underlying**: One symbol per position
3. **Historical IV Estimation**: Uses HV * 1.2 multiplier
4. **No Real Options Data**: Uses Black-Scholes approximation

### Planned Enhancements
1. **American Options**: Add early exercise probability
2. **Real Options Data**: Integrate CBOE or Polygon data
3. **Volatility Smile**: Term structure and skew modeling
4. **Portfolio-Level**: Multi-position correlation analysis
5. **Tax Considerations**: Wash sales, long/short-term gains

---

## References

### Options Pricing
- Black, F., & Scholes, M. (1973). "The Pricing of Options and Corporate Liabilities"
- Hull, J. (2018). "Options, Futures, and Other Derivatives" (10th ed.)

### Greeks
- Natenberg, S. (1994). "Option Volatility and Pricing"
- Cohen, G. (2005). "The Bible of Options Strategies"

### Backtesting
- Pardo, R. (2008). "The Evaluation and Optimization of Trading Strategies"
- Chan, E. (2013). "Algorithmic Trading: Winning Strategies"

---

## Support

For questions or issues:
1. Check test files for usage examples
2. Review sample strategies in `run_options_backtest.py`
3. Refer to inline documentation in source code

---

**End of Documentation**
