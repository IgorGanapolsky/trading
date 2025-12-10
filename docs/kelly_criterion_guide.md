# Kelly Criterion Position Sizing Guide

## Overview

The Kelly Criterion is now integrated into the RiskManager (`src/core/risk_manager.py`) to provide optimal position sizing based on historical performance.

**Formula**: `Kelly % = W - [(1-W)/R]`

Where:
- **W** = Win probability (historical win rate)
- **R** = Win/Loss ratio (average win / average loss)

## Key Features

### 1. Conservative Half-Kelly (Recommended)
- Uses 50% of full Kelly to reduce volatility
- Better risk-adjusted returns in practice
- Default setting: `use_half_kelly=True`

### 2. Position Size Caps
- Default maximum: 25% of portfolio
- Prevents over-leverage even with high Kelly values
- Configurable via `max_kelly_cap` parameter

### 3. Negative Expectancy Protection
- Returns 0% allocation for losing strategies
- Prevents trading when Kelly < 0 (negative edge)

## Usage Examples

### Example 1: Calculate Kelly Fraction

```python
from src.core.risk_manager import RiskManager

risk_mgr = RiskManager()

# With explicit win rate and win/loss ratio
kelly_frac = risk_mgr.calculate_kelly_fraction(
    win_rate=0.62,          # 62% win rate
    win_loss_ratio=1.5,     # Wins are 1.5x larger than losses
    use_half_kelly=True,    # Conservative half-Kelly
    max_kelly_cap=0.25      # Cap at 25% of portfolio
)

print(f"Recommended allocation: {kelly_frac:.2%}")
# Output: Recommended allocation: 18.33%
```

### Example 2: Kelly-Adjusted Position Size

```python
# Calculate base position
account_value = 100000.0  # $100k portfolio
base_position = 10000.0   # $10k base position

# Apply Kelly adjustment
kelly_adjusted = risk_mgr.kelly_adjusted_size(
    base_position_size=base_position,
    win_rate=0.62,
    win_loss_ratio=1.5,
    use_half_kelly=True
)

print(f"Base: ${base_position:,.2f} → Kelly-adjusted: ${kelly_adjusted:,.2f}")
# Output: Base: $10,000.00 → Kelly-adjusted: $1,833.33
```

### Example 3: Using Historical Trades

```python
# Load historical trades from data files
historical_trades = risk_mgr.get_historical_trades_for_kelly(data_dir="data")

# Calculate Kelly from actual performance
kelly_frac = risk_mgr.calculate_kelly_fraction(
    historical_trades=historical_trades,
    use_half_kelly=True
)

print(f"Kelly from historical data: {kelly_frac:.2%}")
```

### Example 4: Manual Historical Trades

```python
# Or provide trades manually
trades = [
    {"profit_loss": 100},   # Win
    {"profit_loss": -50},   # Loss
    {"profit_loss": 150},   # Win
    {"profit_loss": -40},   # Loss
    {"profit_loss": 120},   # Win
]

kelly_frac = risk_mgr.calculate_kelly_fraction(
    historical_trades=trades,
    use_half_kelly=True
)

# Calculates: 60% win rate, 2.74:1 W/L ratio → 22.7% allocation
```

## Integration with Trading System

### Option A: Apply Kelly to Base Position

```python
# In your trading strategy
risk_mgr = RiskManager()

# Calculate base position using existing logic
base_size = risk_mgr.calculate_position_size(
    account_value=account_value,
    risk_per_trade_pct=1.0,
    price_per_share=current_price
)

# Apply Kelly adjustment
optimal_size = risk_mgr.kelly_adjusted_size(
    base_position_size=base_size,
    win_rate=0.62,
    win_loss_ratio=1.5
)
```

### Option B: Direct Kelly Calculation

```python
# Get Kelly fraction
kelly_frac = risk_mgr.calculate_kelly_fraction(
    win_rate=0.62,
    win_loss_ratio=1.5,
    use_half_kelly=True
)

# Calculate position directly
position_size = account_value * kelly_frac
```

## Best Practices

### 1. Start with Historical Data
```python
# Use actual performance, not assumptions
historical_trades = risk_mgr.get_historical_trades_for_kelly()
kelly_frac = risk_mgr.calculate_kelly_fraction(historical_trades=historical_trades)
```

### 2. Always Use Half-Kelly for Live Trading
```python
# Full Kelly can lead to excessive drawdowns
kelly_frac = risk_mgr.calculate_kelly_fraction(
    win_rate=0.62,
    win_loss_ratio=1.5,
    use_half_kelly=True  # ALWAYS True for live trading
)
```

### 3. Respect the Cap
```python
# Never risk more than 25% on a single trade
kelly_frac = risk_mgr.calculate_kelly_fraction(
    win_rate=0.75,
    win_loss_ratio=3.0,
    use_half_kelly=True,
    max_kelly_cap=0.25  # Hard cap at 25%
)
```

### 4. Monitor Negative Expectancy
```python
kelly_frac = risk_mgr.calculate_kelly_fraction(
    win_rate=0.40,
    win_loss_ratio=1.0
)

if kelly_frac == 0.0:
    # Strategy has negative expectancy - DO NOT TRADE
    print("Strategy is losing money on average - stop trading")
```

## Kelly Results Interpretation

| Kelly Fraction | Interpretation | Action |
|----------------|----------------|--------|
| 0% | Negative expectancy | Stop trading - strategy is losing |
| 1-10% | Small edge | Trade conservatively, small positions |
| 10-20% | Good edge | Moderate positions, typical for most strategies |
| 20-25% | Strong edge | Larger positions, verify data quality |
| >25% (capped) | Very strong edge | Maximum allowed position size |

## Common Scenarios

### Scenario 1: Early R&D Phase (Minimal Data)
```python
# Not enough historical data yet
if len(historical_trades) < 10:
    # Use conservative defaults
    kelly_frac = risk_mgr.calculate_kelly_fraction(
        win_rate=0.50,       # Assume 50% until proven otherwise
        win_loss_ratio=1.0,  # Assume 1:1 until proven otherwise
        use_half_kelly=True
    )
```

### Scenario 2: Mature System with Proven Edge
```python
# 100+ trades, proven strategy
kelly_frac = risk_mgr.calculate_kelly_fraction(
    win_rate=0.62,       # From historical data
    win_loss_ratio=1.5,  # From historical data
    use_half_kelly=True
)
# Result: 18.33% allocation
```

### Scenario 3: Strategy Degradation
```python
# Recent performance dropping
recent_kelly = risk_mgr.calculate_kelly_fraction(
    historical_trades=last_30_trades
)

if recent_kelly < historical_kelly * 0.5:
    print("WARNING: Strategy performance degrading")
    print("Consider reducing position sizes")
```

## Technical Details

### Full vs Half Kelly

```python
# Full Kelly: Maximum growth rate
full_kelly = W - (1-W)/R
# Example: 0.62 - (0.38/1.5) = 0.367 or 36.7%

# Half Kelly: Better risk-adjusted returns
half_kelly = full_kelly / 2
# Example: 36.7% / 2 = 18.33%
```

### Why Half-Kelly?
- **Full Kelly**: Maximizes long-term growth but high volatility
- **Half Kelly**: 75% of growth rate with 50% of volatility
- **Quarter Kelly**: 50% of growth rate with 25% of volatility

### Recommended Approach
- **Paper trading**: Use full Kelly to test
- **Small accounts (<$10k)**: Use half Kelly
- **Large accounts (>$10k)**: Use half Kelly or quarter Kelly

## Error Handling

The implementation handles edge cases gracefully:

```python
# No historical data
kelly = risk_mgr.calculate_kelly_fraction(historical_trades=[])
# Returns: 0.0

# Invalid win rate
kelly = risk_mgr.calculate_kelly_fraction(win_rate=1.5, win_loss_ratio=1.0)
# Logs warning, returns: 0.0

# Negative expectancy
kelly = risk_mgr.calculate_kelly_fraction(win_rate=0.40, win_loss_ratio=1.0)
# Logs info about negative expectancy, returns: 0.0
```

## Logging

Kelly calculations are fully logged for debugging:

```
INFO: Kelly Criterion: 18.33% (win_rate=62.00%, W/L ratio=1.50, half_kelly=True, cap=25.00%)
INFO: Kelly position sizing: $10000.00 → $1833.33 (Kelly fraction: 18.33%)
```

## Testing

Run the integration tests:

```bash
python3 test_kelly_integration.py
```

Or test the RiskManager directly:

```bash
python3 src/core/risk_manager.py
```

## References

- **Original Paper**: Kelly, J. L. (1956). "A New Interpretation of Information Rate"
- **Practical Application**: Thorp, E. O. (1969). "Optimal Gambling Systems for Favorable Games"
- **Risk Management**: Poundstone, W. (2005). "Fortune's Formula"

## Support

For questions or issues:
1. Check the example tests in `test_kelly_integration.py`
2. Review the docstrings in `src/core/risk_manager.py`
3. Run the standalone examples: `python3 src/core/risk_manager.py`
