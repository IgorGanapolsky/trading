# Fibonacci Auto-Scaling System

## Overview

The Fibonacci Auto-Scaling system implements a profit-based compounding strategy for daily investments. Each investment level is funded ONLY by actual profits from previous levels, ensuring zero additional capital injection.

**North Star Goal**: Scale from $1/day to $100/day through compound returns.

## Fibonacci Sequence

```python
FIBONACCI = [1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 100]
FUNDING_DAYS = 30  # Days of funding required per level
MAX_DAILY = 100.0  # Safety cap
```

## Scaling Milestones

| Level | Daily Amount | Profit Required | Formula | Description |
|-------|-------------|-----------------|---------|-------------|
| 0 | $1/day | $0 | Base level | Starting point |
| 1 | $2/day | $60 | $2 × 30 | 2x scale-up |
| 2 | $3/day | $90 | $3 × 30 | 50% increase |
| 3 | $5/day | $150 | $5 × 30 | 67% increase |
| 4 | $8/day | $240 | $8 × 30 | 60% increase |
| 5 | $13/day | $390 | $13 × 30 | 62% increase |
| 6 | $21/day | $630 | $21 × 30 | 62% increase |
| 7 | $34/day | $1,020 | $34 × 30 | 62% increase |
| 8 | $55/day | $1,650 | $55 × 30 | 62% increase |
| 9 | $89/day | $2,670 | $89 × 30 | 62% increase |
| 10 | $100/day | $3,000 | $100 × 30 | Final cap |

## Core Principle

**Each level must generate 30 days of funding for the NEXT level.**

Example: To scale from $1/day to $2/day, you need $60 cumulative profit ($2 × 30 days).

This ensures sustainable compounding without external capital.

## API Reference

### Class: `FibonacciScaler`

#### Initialization

```python
from scripts.financial_automation import FibonacciScaler

scaler = FibonacciScaler(paper=True, state_file="data/fibonacci_scaling_state.json")
```

**Parameters:**
- `paper` (bool): Whether to use paper trading mode (default: True)
- `state_file` (str): Path to state persistence file

#### Convenience API (Recommended)

These methods read from system state automatically - no parameters needed!

##### `get_current_level() -> int`

Get current Fibonacci level index (0-10).

```python
level = scaler.get_current_level()
# Returns: 0 (for $1/day), 1 (for $2/day), etc.
```

##### `get_daily_amount() -> float`

Get current daily investment amount in dollars.

```python
amount = scaler.get_daily_amount()
# Returns: 1.0, 2.0, 3.0, 5.0, 8.0, etc.
```

##### `get_next_milestone() -> dict`

Get details about the next scaling milestone.

```python
milestone = scaler.get_next_milestone()
# Returns:
# {
#     "at_max": False,
#     "current_level": 1,
#     "next_level": 2,
#     "required_profit": 60.0,
#     "current_profit": 45.50,
#     "remaining": 14.50,
#     "progress_pct": 75.8,
#     "message": "Need $60.00 profit to scale to $2/day ($14.50 remaining)"
# }
```

##### `should_scale_up() -> bool`

Check if ready to scale up to next level.

```python
if scaler.should_scale_up():
    print("Ready to scale!")
```

##### `scale_up() -> dict`

Execute scale-up to next Fibonacci level.

```python
result = scaler.scale_up()
# Returns:
# {
#     "scaled": True,
#     "old_amount": 1,
#     "new_amount": 2,
#     "old_level": 0,
#     "new_level": 1,
#     "profit_at_scale": 65.50,
#     "milestone_hit": 60.0,
#     "timestamp": "2025-12-02T10:30:00"
# }
```

Or if not ready:
```python
# {
#     "scaled": False,
#     "reason": "Milestone not reached",
#     "current_profit": 45.50,
#     "required_profit": 60.0,
#     "remaining": 14.50
# }
```

##### `get_projection(avg_daily_return_pct=0.13) -> dict`

Project time to reach $100/day goal.

```python
projection = scaler.get_projection(avg_daily_return_pct=0.13)
# Returns:
# {
#     "current_level": 1,
#     "current_profit": 45.50,
#     "avg_daily_return_pct": 0.13,
#     "current_equity": 100045.50,
#     "days_to_max": 485,
#     "months_to_max": 16.2,
#     "date_at_max": "2026-04-01",
#     "max_daily_amount": 100.0,
#     "milestones": [
#         {
#             "level_index": 0,
#             "daily_amount": 1,
#             "milestone_profit": 30,
#             "days_from_now": 0,
#             "months_from_now": 0.0,
#             "date_estimate": "2025-12-02"
#         },
#         # ... more milestones
#     ],
#     "note": "Assumes 0.13% daily return (compounding). Actual timeline may vary."
# }
```

#### Legacy API (Backwards Compatible)

These methods require parameters and are kept for compatibility:

```python
# Legacy methods (still work)
level = scaler.get_fibonacci_level(cumulative_profit=65.50)
milestone = scaler.get_next_milestone(current_level=2.0)
should_scale = scaler.should_scale_up(cumulative_profit=65.50, current_level=2.0)
result = scaler.calculate_daily_investment()
```

## Example Usage

### Basic Usage

```python
from scripts.financial_automation import FibonacciScaler

# Initialize
scaler = FibonacciScaler(paper=True)

# Check current status
level = scaler.get_current_level()
amount = scaler.get_daily_amount()
print(f"Currently at Level {level}: ${amount:.0f}/day")

# Check progress to next level
milestone = scaler.get_next_milestone()
print(f"Progress: {milestone['progress_pct']:.1f}%")
print(f"Need ${milestone['remaining']:.2f} more profit to scale up")

# Auto-scale if ready
if scaler.should_scale_up():
    result = scaler.scale_up()
    print(f"🚀 Scaled up to ${result['new_amount']}/day!")
```

### Projection Analysis

```python
# Project timeline to $100/day goal
projection = scaler.get_projection(avg_daily_return_pct=0.13)

print(f"Current Level: ${projection['current_level']:.0f}/day")
print(f"Time to $100/day: {projection['months_to_max']:.1f} months")
print(f"Estimated Date: {projection['date_at_max']}")

# Show all milestones
print("\nMilestone Timeline:")
for m in projection['milestones']:
    print(f"  ${m['daily_amount']:3.0f}/day → {m['months_from_now']:4.1f} months → {m['date_estimate']}")
```

### Integration with Automation

```python
def daily_trading_routine():
    """Daily trading with auto-scaling."""
    scaler = FibonacciScaler(paper=True)

    # Get today's investment amount
    daily_amount = scaler.get_daily_amount()

    # Execute trades with this amount
    execute_trades(daily_amount)

    # Check for auto-scale after trading
    if scaler.should_scale_up():
        result = scaler.scale_up()
        send_notification(f"Auto-scaled to ${result['new_amount']}/day!")
```

## State Persistence

The scaler maintains state in two files:

1. **fibonacci_scaling_state.json** - Scaling history and current level
   ```json
   {
     "fibonacci_level": 2,
     "current_level": 3.0,
     "last_scale_up": "2025-12-02T10:30:00",
     "scale_up_history": [
       {
         "timestamp": "2025-11-15T09:00:00",
         "old_level": 1.0,
         "new_level": 2.0,
         "cumulative_profit": 62.50,
         "milestone_hit": 60.0
       }
     ]
   }
   ```

2. **system_state.json** - Overall system state (profit tracking)
   - Reads `account.total_pl` for cumulative profit
   - Used to determine current Fibonacci level

## Testing

Run the test suite:

```bash
python tests/test_fibonacci_scaler.py
```

Tests verify:
- ✅ Current level calculation
- ✅ Daily amount retrieval
- ✅ Milestone tracking
- ✅ Scale-up logic
- ✅ Projection accuracy
- ✅ Threshold correctness

## Safety Features

1. **Safety Cap**: Maximum $100/day prevents over-leveraging
2. **Profit-Funded Only**: No external capital added after initial investment
3. **30-Day Funding Rule**: Ensures each level is fully backed by previous profits
4. **State Persistence**: Survives restarts and crashes
5. **Audit Trail**: All scale-ups logged with timestamps

## Mathematical Foundation

### Compounding Formula

```
Level_n_profit = Fibonacci[n] × 30 days

To reach $100/day from $1/day:
- Starting equity: $100,000
- Daily return: 0.13% (realistic target)
- Daily profit: $100,000 × 0.0013 = $130/day
- Time to $3,000 profit: ~23 days
- Time to reach each milestone: ~16-18 months total
```

### Why Fibonacci?

1. **Natural Scaling**: Each level is ~60% larger than previous
2. **Risk-Adjusted**: Not too aggressive (avoid 2x jumps after $8/day)
3. **Mathematically Elegant**: Well-studied sequence with proven properties
4. **Milestone Clarity**: Clear targets for scaling decisions

## Comparison to Linear Scaling

| Metric | Fibonacci | Linear ($10 increments) |
|--------|-----------|-------------------------|
| Starting amount | $1/day | $10/day |
| Scale-up logic | Profit-based | Fixed increments |
| Capital requirement | Zero (profit-funded) | External capital needed |
| Risk management | Conservative (62% jumps) | Aggressive (100% jumps) |
| Max level | $100/day | Unlimited (risky) |
| Psychological wins | 11 milestones | Fewer milestones |

## Best Practices

1. **Don't Skip Levels**: Each level must be fully funded
2. **Monitor Progress**: Check `get_next_milestone()` daily
3. **Celebrate Wins**: Each scale-up is a validated achievement
4. **Project Forward**: Use `get_projection()` for goal-setting
5. **Trust the Process**: Let profits compound naturally

## Troubleshooting

### "Milestone not reached"
- Check current profit: `milestone['current_profit']`
- Verify target: `milestone['required_profit']`
- Calculate remaining: `milestone['remaining']`

### "At maximum level"
- Congratulations! You've hit $100/day
- Consider increasing safety cap or compounding at max level

### Projection shows "Beyond 10 years"
- Current return rate may be too low
- Adjust `avg_daily_return_pct` parameter
- Focus on improving win rate and Sharpe ratio

## Future Enhancements

- [ ] Multi-asset scaling (different Fibonacci tracks per strategy)
- [ ] Dynamic funding days (adjust based on volatility)
- [ ] Reverse scaling on drawdowns (safety feature)
- [ ] Integration with Kelly Criterion for optimal sizing
- [ ] Machine learning for return rate predictions

## References

- North Star Goal: `.claude/CLAUDE.md` (Fibonacci Compounding Strategy)
- Financial Automation: `scripts/financial_automation.py`
- System State: `data/system_state.json`
- R&D Phase: `docs/r-and-d-phase.md`

---

**Last Updated**: December 2, 2025
**Version**: 1.0
**Status**: Production Ready ✅
