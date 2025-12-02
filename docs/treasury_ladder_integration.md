# Treasury Ladder Strategy Integration Guide

## Overview

The Treasury Ladder Strategy (`src/strategies/treasury_ladder_strategy.py`) implements a 3-tier treasury ETF ladder with dynamic allocation based on yield curve analysis. It provides stable income and capital preservation while adapting to interest rate environments.

**File Location**: `/home/user/trading/src/strategies/treasury_ladder_strategy.py`

## Strategy Details

### Treasury ETFs

- **SHY**: iShares 1-3 Year Treasury Bond ETF (short-term, low duration)
- **IEF**: iShares 7-10 Year Treasury Bond ETF (intermediate duration)
- **TLT**: iShares 20+ Year Treasury Bond ETF (long-term, high duration)

### Allocation Logic

The strategy adjusts allocation based on yield curve regime:

| Regime | Condition | SHY | IEF | TLT | Rationale |
|--------|-----------|-----|-----|-----|-----------|
| **Normal** | 10yr - 2yr > 0.5% | 40% | 40% | 20% | Balanced ladder |
| **Flat** | 0% < spread < 0.5% | 50% | 35% | 15% | Slight shift to short duration |
| **Inverted** | 10yr - 2yr < 0% | 70% | 25% | 5% | Heavy recession hedge |

### Key Features

1. **Yield Curve Detection**: Uses FRED API (DGS2, DGS10, T10Y2Y) for real-time treasury yields
2. **Dynamic Allocation**: Automatically shifts allocation based on yield curve shape
3. **Automatic Rebalancing**: Triggers when allocation drifts >5% from target
4. **Risk Management**: Low-risk, government-backed securities only
5. **Alpaca Integration**: Fractional share trading via Alpaca API

## Usage Examples

### Standalone Usage

```python
from src.strategies.treasury_ladder_strategy import TreasuryLadderStrategy

# Initialize strategy
strategy = TreasuryLadderStrategy(
    daily_allocation=10.0,      # $10/day
    rebalance_threshold=0.05,   # 5% drift triggers rebalance
    paper=True                  # Paper trading mode
)

# 1. Analyze yield curve
regime, spread, rationale = strategy.analyze_yield_curve()
print(f"Yield curve: {regime.value}, spread: {spread:.2f}%")

# 2. Get optimal allocation
allocation = strategy.get_optimal_allocation()
print(f"SHY: {allocation.shy_pct*100:.0f}%, IEF: {allocation.ief_pct*100:.0f}%, TLT: {allocation.tlt_pct*100:.0f}%")

# 3. Execute daily investment
result = strategy.execute_daily(amount=10.0)
print(f"Invested: ${result['total_invested']:.2f}, Orders: {len(result['orders'])}")

# 4. Check and rebalance if needed
decision = strategy.rebalance_if_needed()
if decision and decision.should_rebalance:
    print(f"Rebalanced: {decision.reason}")

# 5. Get performance summary
summary = strategy.get_performance_summary()
print(f"Total value: ${summary['total_market_value']:.2f}, Return: {summary['return_pct']:.2f}%")
```

### Demo Script

A complete demo script is available at `examples/treasury_ladder_demo.py`:

```bash
# Dry run (analysis only, no trades)
python3 examples/treasury_ladder_demo.py --dry-run

# Execute daily $10 investment
python3 examples/treasury_ladder_demo.py --execute --amount 10.0

# Check and execute rebalancing
python3 examples/treasury_ladder_demo.py --rebalance

# Get performance summary
python3 examples/treasury_ladder_demo.py --summary

# Verbose mode
python3 examples/treasury_ladder_demo.py --dry-run -v
```

## Integration into Core Trading System

### Option 1: Add to Core Strategy Diversification

The Core Strategy (`src/strategies/core_strategy.py`) already has treasury allocation. You can replace or complement the existing `TLT/IEF` allocation with the ladder strategy.

**In `core_strategy.py`**:

```python
from src.strategies.treasury_ladder_strategy import TreasuryLadderStrategy

class CoreStrategy:
    def __init__(self, ...):
        # ... existing init code ...

        # Initialize treasury ladder
        self.treasury_ladder = TreasuryLadderStrategy(
            daily_allocation=self.daily_allocation * self.TREASURY_ALLOCATION_PCT,
            rebalance_threshold=0.05,
            paper=True
        )

    def execute_daily(self):
        # ... existing execution code ...

        # Execute treasury ladder allocation
        treasury_amount = self.daily_allocation * self.TREASURY_ALLOCATION_PCT
        treasury_result = self.treasury_ladder.execute_daily(amount=treasury_amount)

        # Check weekly rebalancing (e.g., every Monday)
        if datetime.now().weekday() == 0:  # Monday
            self.treasury_ladder.rebalance_if_needed()
```

### Option 2: Standalone Tier 1b Strategy

Add as a separate conservative strategy alongside Core Strategy:

**In `main.py` or orchestrator**:

```python
from src.strategies.treasury_ladder_strategy import TreasuryLadderStrategy

# Initialize strategies
core_strategy = CoreStrategy(daily_allocation=6.0)  # 60% of $10
treasury_strategy = TreasuryLadderStrategy(daily_allocation=4.0)  # 40% of $10

# Daily execution
core_result = core_strategy.execute_daily()
treasury_result = treasury_strategy.execute_daily()

# Weekly rebalancing (Mondays)
if datetime.now().weekday() == 0:
    treasury_strategy.rebalance_if_needed()
```

### Option 3: As Part of Diversification Allocation

Use for the existing 10% treasury allocation in Core Strategy:

```python
# In CoreStrategy.execute_daily()

# Calculate treasury allocation (10% of daily)
treasury_amount = effective_allocation * self.TREASURY_ALLOCATION_PCT

# Execute via ladder strategy
if not hasattr(self, '_treasury_ladder'):
    from src.strategies.treasury_ladder_strategy import TreasuryLadderStrategy
    self._treasury_ladder = TreasuryLadderStrategy(
        daily_allocation=treasury_amount,
        paper=self.alpaca_trader.paper
    )

treasury_result = self._treasury_ladder.execute_daily(amount=treasury_amount)
```

## Scheduled Execution

### Using APScheduler (Legacy Main)

```python
import schedule
from src.strategies.treasury_ladder_strategy import TreasuryLadderStrategy

strategy = TreasuryLadderStrategy(daily_allocation=10.0)

# Daily investment at 9:35 AM ET
schedule.every().day.at("09:35").do(strategy.execute_daily)

# Weekly rebalancing on Mondays at 10:00 AM ET
schedule.every().monday.at("10:00").do(strategy.rebalance_if_needed)

while True:
    schedule.run_pending()
    time.sleep(60)
```

### Using Cron

```bash
# Daily execution at 9:35 AM ET
35 9 * * 1-5 cd /home/user/trading && python3 examples/treasury_ladder_demo.py --execute --amount 10.0

# Weekly rebalancing on Mondays at 10:00 AM ET
0 10 * * 1 cd /home/user/trading && python3 examples/treasury_ladder_demo.py --rebalance
```

## Configuration

### Environment Variables

Required:
```bash
# Alpaca API credentials
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
```

Optional:
```bash
# FRED API for yield curve data (free at https://fred.stlouisfed.org/docs/api/api_key.html)
FRED_API_KEY=your_fred_key_here

# Daily investment amount
DAILY_INVESTMENT=10.0
```

### Strategy Parameters

```python
TreasuryLadderStrategy(
    daily_allocation=10.0,              # Daily investment amount
    rebalance_threshold=0.05,           # 5% drift triggers rebalance
    paper=True                          # Paper trading mode
)
```

## Performance Monitoring

### Get Performance Summary

```python
summary = strategy.get_performance_summary()

print(f"Total invested:       ${summary['total_invested']:.2f}")
print(f"Market value:         ${summary['total_market_value']:.2f}")
print(f"Cost basis:           ${summary['total_cost_basis']:.2f}")
print(f"Unrealized P/L:       ${summary['total_unrealized_pl']:.2f}")
print(f"Return:               {summary['return_pct']:.2f}%")
print(f"Current regime:       {summary['current_regime']}")
print(f"Last rebalance:       {summary['last_rebalance']}")
print(f"Rebalance count:      {summary['rebalance_count']}")
```

### Rebalancing History

```python
# View rebalancing decisions
for decision in strategy.rebalance_history:
    print(f"{decision.timestamp}: {decision.reason}")
    print(f"  Max drift: {decision.max_drift*100:.1f}%")
    print(f"  Rebalanced: {decision.should_rebalance}")
```

## Research Context (Dec 2025)

- **Current yields**: 2-year ~4.17%, 10-year ~4.19%, 30-year ~4.36%
- **Yield curve**: Nearly flat (10yr-2yr spread ~0.02%)
- **Fed outlook**: Expected rate cuts, but long-term settling around 3-4%
- **Strategy**: Provides stable income and capital preservation in volatile markets

## Technical Details

### Class Hierarchy

```
TreasuryLadderStrategy
├── ETF_SYMBOLS = ["SHY", "IEF", "TLT"]
├── ALLOCATION_NORMAL = {SHY: 40%, IEF: 40%, TLT: 20%}
├── ALLOCATION_FLAT = {SHY: 50%, IEF: 35%, TLT: 15%}
├── ALLOCATION_INVERTED = {SHY: 70%, IEF: 25%, TLT: 5%}
├── analyze_yield_curve() -> (regime, spread, rationale)
├── get_optimal_allocation() -> TreasuryAllocation
├── execute_daily(amount) -> Dict[execution_results]
├── rebalance_if_needed() -> RebalanceDecision
└── get_performance_summary() -> Dict[performance_metrics]
```

### Data Classes

```python
@dataclass
class YieldCurveRegime(Enum):
    NORMAL = "normal"
    FLAT = "flat"
    INVERTED = "inverted"

@dataclass
class TreasuryAllocation:
    shy_pct: float
    ief_pct: float
    tlt_pct: float
    regime: YieldCurveRegime
    spread: float
    rationale: str
    timestamp: datetime

@dataclass
class RebalanceDecision:
    should_rebalance: bool
    current_allocation: Dict[str, float]
    target_allocation: Dict[str, float]
    drift_pct: Dict[str, float]
    max_drift: float
    reason: str
    timestamp: datetime
```

## Dependencies

- **alpaca-py**: For trading execution
- **yfinance**: For market data (fallback)
- **requests**: For FRED API calls
- **python-dotenv**: For environment configuration

All dependencies are already in the project's requirements.

## Testing

```bash
# Run unit tests (if available)
pytest tests/test_treasury_ladder_strategy.py -v

# Manual testing with dry run
python3 examples/treasury_ladder_demo.py --dry-run -v

# Test with small amount (paper trading)
python3 examples/treasury_ladder_demo.py --execute --amount 1.0 -v
```

## Future Enhancements

1. **Duration Targeting**: Allow specifying target portfolio duration
2. **Tax Optimization**: Consider tax implications of rebalancing
3. **Yield Optimization**: Add optimization for yield vs. duration trade-off
4. **Multi-Currency**: Support international treasury bonds
5. **Custom Ladders**: Allow user-defined ladder rungs and allocations
6. **Historical Backtesting**: Add backtesting module for strategy validation

## Support

For issues or questions:
- Check logs in `/home/user/trading/logs/`
- Review FRED API status: https://fred.stlouisfed.org/docs/api/fred/
- Check Alpaca API status: https://status.alpaca.markets/

## References

- FRED API Documentation: https://fred.stlouisfed.org/docs/api/fred/
- Alpaca API Documentation: https://docs.alpaca.markets/
- Treasury ETF Information:
  - SHY: https://www.ishares.com/us/products/239452/
  - IEF: https://www.ishares.com/us/products/239456/
  - TLT: https://www.ishares.com/us/products/239454/
