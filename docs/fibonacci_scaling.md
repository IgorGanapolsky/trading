# Fibonacci Scaling Strategy

## Overview

The Fibonacci Scaling strategy is a profit-based investment scaling system where each increase in daily investment is funded **ONLY** by actual profits from previous levels. This ensures sustainable growth without requiring additional external capital.

## Strategy Details

### Fibonacci Sequence

Daily investment amounts follow the Fibonacci sequence:
```
$1, $2, $3, $5, $8, $13, $21, $34, $55, $89, $100 (capped)
```

### Scaling Rules

**Core Principle**: Scale up when `cumulative_profit >= next_level × 30 days`

**Examples**:
- **$1/day → $2/day**: When profit ≥ $60 ($2 × 30 days)
- **$2/day → $3/day**: When profit ≥ $90 ($3 × 30 days)
- **$3/day → $5/day**: When profit ≥ $150 ($5 × 30 days)
- **$5/day → $8/day**: When profit ≥ $240 ($8 × 30 days)

### Safety Cap

Maximum daily investment: **$100/day**

This cap prevents over-leverage while still allowing significant scaling.

## Implementation

### File Structure

```
scripts/financial_automation.py
├── FibonacciScaler (primary class)
├── DynamicInvestmentScaler (deprecated, kept for compatibility)
└── run_all_automation() (updated to use FibonacciScaler)

data/fibonacci_scaling_state.json (scaling state & history)
```

### Key Methods

#### `get_fibonacci_level(cumulative_profit: float) -> float`

Returns the current daily investment amount based on cumulative profit.

**Logic**:
1. If profit ≤ 0, return $1/day (base level)
2. Find highest Fibonacci level where profit ≥ milestone
3. Milestone = daily_amount × 30 days

**Example**:
```python
scaler = FibonacciScaler()
level = scaler.get_fibonacci_level(150.0)  # Returns 5.0 ($5/day)
```

#### `get_next_milestone(current_level: float) -> dict`

Returns information about the next scaling milestone.

**Returns**:
```python
{
    "next_level": 8.0,
    "milestone_profit": 240.0,
    "current_level": 5.0,
    "at_max": False,
    "days_to_fund": 30,
    "message": "Need $240.00 cumulative profit to scale to $8/day"
}
```

#### `should_scale_up(cumulative_profit: float, current_level: float) -> bool`

Determines if the system should scale up to the next level.

**Example**:
```python
should_scale = scaler.should_scale_up(240.0, 5.0)  # Returns True (hit $8 milestone)
```

#### `calculate_daily_investment() -> dict`

Main method that:
1. Fetches current account data from Alpaca API
2. Loads cumulative profit from system_state.json
3. Calculates current Fibonacci level
4. Detects scale-up events
5. Logs scale-ups to audit trail
6. Returns detailed scaling information

**Returns**:
```python
{
    "daily_amount": 5.0,
    "cumulative_profit": 150.0,
    "current_level": 5.0,
    "previous_level": 3.0,
    "scaled_up": True,  # If just scaled up
    "next_level": 8.0,
    "next_milestone": 240.0,
    "profit_to_next_level": 90.0,
    "progress_to_next": 62.5,  # Percent progress
    "at_max_level": False,
    "fibonacci_sequence": [1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 100],
    "scaling_strategy": "Fibonacci Compounding (each level funded by previous profits)"
}
```

## Usage

### Basic Usage

```python
from scripts.financial_automation import FibonacciScaler

# Initialize scaler
scaler = FibonacciScaler(paper=True)

# Calculate today's investment
result = scaler.calculate_daily_investment()

print(f"Today's investment: ${result['daily_amount']:.2f}/day")
print(f"Progress to next level: {result['progress_to_next']:.1f}%")
print(f"Need ${result['profit_to_next_level']:.2f} more to scale up")
```

### Integration with Trading System

```python
# In main trading loop
scaler = FibonacciScaler(paper=False)
investment_data = scaler.calculate_daily_investment()

daily_amount = investment_data['daily_amount']

# Split across tiers
tier1_amount = daily_amount * 0.67  # Core ETFs
tier2_amount = daily_amount * 0.33  # Growth stocks

# Execute trades
execute_tier1_trades(tier1_amount)
execute_tier2_trades(tier2_amount)
```

### Monitoring Scale-Up Events

Scale-up events are automatically logged to:
1. **Console**: `logger.info()` message
2. **State file**: `data/fibonacci_scaling_state.json`

**State file structure**:
```json
{
  "current_level": 5.0,
  "last_scale_up": "2025-12-02T10:30:00",
  "scale_up_history": [
    {
      "timestamp": "2025-11-15T09:35:00",
      "old_level": 1.0,
      "new_level": 2.0,
      "cumulative_profit": 60.0,
      "milestone_hit": 60.0
    },
    {
      "timestamp": "2025-11-28T09:35:00",
      "old_level": 2.0,
      "new_level": 3.0,
      "cumulative_profit": 90.0,
      "milestone_hit": 90.0
    }
  ]
}
```

## Testing

### Run Test Suite

```bash
python3 test_fibonacci_scaling.py
```

**Tests include**:
- No profit (stay at $1/day)
- Partial progress scenarios
- Hitting each milestone
- At maximum level ($100/day)

### Run Demo with Current State

```bash
python3 demo_fibonacci_scaling.py
```

Shows:
- Current profit and Fibonacci level
- Progress to next milestone
- Complete roadmap of all levels
- Projection based on 10% monthly returns

## Fibonacci Milestone Table

| Level | Daily $ | Milestone $ | Days to Fund | Cumulative Days |
|-------|---------|-------------|--------------|-----------------|
| 1     | $1      | $30         | 30           | 30              |
| 2     | $2      | $60         | 30           | 60              |
| 3     | $3      | $90         | 30           | 90              |
| 4     | $5      | $150        | 30           | 120             |
| 5     | $8      | $240        | 30           | 150             |
| 6     | $13     | $390        | 30           | 180             |
| 7     | $21     | $630        | 30           | 210             |
| 8     | $34     | $1,020      | 30           | 240             |
| 9     | $55     | $1,650      | 30           | 270             |
| 10    | $89     | $2,670      | 30           | 300             |
| 11    | $100    | $3,000      | 30           | 330             |

## Current Status (as of Dec 2, 2025)

- **Current Level**: $1/day
- **Cumulative Profit**: $5.50
- **Next Milestone**: $60 (for $2/day)
- **Progress**: 9.2% ($54.50 to go)

## Advantages

1. **Zero External Capital Required**: Each scale funded purely by profits
2. **Sustainable Growth**: Can't over-leverage beyond earned profits
3. **Automatic Risk Management**: Scales down during drawdowns
4. **Clear Milestones**: Objective, quantifiable scaling criteria
5. **Exponential Potential**: Fibonacci growth compounds faster than linear

## Comparison: Linear vs Fibonacci

### Linear Scaling (Old Method)
```
Formula: daily = $10 + 0.3 × floating_pnl
Cap: $50/day
```

**Issues**:
- Tied to floating P/L (unrealized gains)
- Can scale prematurely on temporary gains
- Lower maximum ($50 vs $100)

### Fibonacci Scaling (New Method)
```
Formula: Based on cumulative profit milestones
Cap: $100/day
```

**Advantages**:
- Tied to actual cumulative profit (realized + unrealized)
- Requires sustained profitability to scale
- Higher potential ($100/day)
- Clear, predictable milestones

## Migration

The old `DynamicInvestmentScaler` is **DEPRECATED** but kept for backward compatibility.

**To migrate**:
```python
# Old way (deprecated)
scaler = DynamicInvestmentScaler(paper=True)

# New way (recommended)
scaler = FibonacciScaler(paper=True)

# Both use same interface
result = scaler.calculate_daily_investment()
```

## Future Enhancements

1. **Dynamic milestone periods**: Adjust from 30 days based on volatility
2. **Multiple sequences**: Different Fibonacci sequences for different strategies
3. **Auto-scaling**: Automatically adjust daily amounts without manual intervention
4. **Backtesting**: Historical analysis of Fibonacci vs linear scaling

## References

- North Star Goal: `/home/user/trading/.claude/CLAUDE.md`
- Implementation: `/home/user/trading/scripts/financial_automation.py`
- Tests: `/home/user/trading/test_fibonacci_scaling.py`
- Demo: `/home/user/trading/demo_fibonacci_scaling.py`

---

**Last Updated**: December 2, 2025
**Status**: ✅ Implemented & Tested
**Next Review**: After hitting first milestone ($60 profit → $2/day)
