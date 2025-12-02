# Fibonacci Scaling Integration Guide

Quick guide for integrating Fibonacci scaling into the trading system.

---

## Quick Integration Steps

### 1. Import the Scaler

```python
from scripts.financial_automation import FibonacciScaler
```

### 2. Initialize (Once per Session)

```python
# Paper trading
scaler = FibonacciScaler(paper=True)

# Live trading
scaler = FibonacciScaler(paper=False)
```

### 3. Get Daily Amount

```python
# Calculate today's investment
result = scaler.calculate_daily_investment()

# Extract the daily amount
daily_amount = result['daily_amount']

# Example: $1.00, $2.00, $3.00, etc.
print(f"Today's budget: ${daily_amount:.2f}")
```

### 4. Split Across Tiers

```python
# Tier 1: Core ETFs (67%)
tier1_amount = daily_amount * 0.67

# Tier 2: Growth Stocks (33%)
tier2_amount = daily_amount * 0.33

print(f"Tier 1 (ETFs): ${tier1_amount:.2f}")
print(f"Tier 2 (Growth): ${tier2_amount:.2f}")
```

### 5. Execute Trades

```python
# Use the amounts in your trading logic
execute_core_etf_trades(tier1_amount)
execute_growth_stock_trades(tier2_amount)
```

---

## Full Example

```python
#!/usr/bin/env python3
"""
Example: Daily Trading with Fibonacci Scaling
"""

from scripts.financial_automation import FibonacciScaler
from src.core.alpaca_trader import AlpacaTrader

def daily_trading_execution():
    """Execute daily trades with Fibonacci-scaled amounts."""

    # Initialize
    scaler = FibonacciScaler(paper=True)
    trader = AlpacaTrader(paper=True)

    # Get today's investment amount
    fib_result = scaler.calculate_daily_investment()

    # Check for errors
    if "error" in fib_result:
        print(f"Error: {fib_result['error']}")
        print(f"Using fallback: ${fib_result['daily_amount']:.2f}")

    daily_amount = fib_result['daily_amount']

    # Log Fibonacci status
    print(f"💎 Fibonacci Scaling Status:")
    print(f"  Daily Amount: ${daily_amount:.2f}")
    print(f"  Current Level: ${fib_result['current_level']:.0f}/day")
    print(f"  Cumulative Profit: ${fib_result['cumulative_profit']:.2f}")
    print(f"  Progress to Next: {fib_result['progress_to_next']:.1f}%")

    # Check for scale-up event
    if fib_result.get('scaled_up'):
        print(f"✨ SCALE-UP! ${fib_result['previous_level']:.0f} → ${fib_result['current_level']:.0f}/day")

    # Split across tiers
    tier1_amount = daily_amount * 0.67  # Core ETFs
    tier2_amount = daily_amount * 0.33  # Growth stocks

    # Execute trades
    print(f"\n📊 Executing Trades:")
    print(f"  Tier 1 (ETFs): ${tier1_amount:.2f}")
    print(f"  Tier 2 (Growth): ${tier2_amount:.2f}")

    # Your existing trading logic here...
    # Example:
    # execute_tier1_trades(trader, tier1_amount)
    # execute_tier2_trades(trader, tier2_amount)

    return {
        "daily_amount": daily_amount,
        "tier1": tier1_amount,
        "tier2": tier2_amount,
        "fibonacci_status": fib_result
    }


if __name__ == "__main__":
    result = daily_trading_execution()
    print(f"\n✅ Daily execution complete")
    print(f"   Total invested: ${result['daily_amount']:.2f}")
```

---

## Monitoring Scale-Up Events

### Check Current Status

```python
result = scaler.calculate_daily_investment()

print(f"Current Level: ${result['current_level']:.0f}/day")
print(f"Next Level: ${result['next_level']:.0f}/day")
print(f"Next Milestone: ${result['next_milestone']:.2f} profit")
print(f"Progress: {result['progress_to_next']:.1f}%")
```

### Detect Scale-Up

```python
if result.get('scaled_up'):
    # A scale-up just occurred!
    old = result['previous_level']
    new = result['current_level']
    profit = result['cumulative_profit']

    print(f"🚀 SCALE-UP EVENT!")
    print(f"   ${old:.0f}/day → ${new:.0f}/day")
    print(f"   Triggered by ${profit:.2f} cumulative profit")

    # Send notification, log to CEO report, etc.
    send_scale_up_notification(old, new, profit)
```

### Check if Close to Milestone

```python
profit_needed = result['profit_to_next_level']
progress = result['progress_to_next']

if progress >= 80:
    print(f"⚠️  Close to next level!")
    print(f"   Only ${profit_needed:.2f} away from ${result['next_level']:.0f}/day")
```

---

## Integration with CEO Reports

Add Fibonacci status to daily reports:

```python
def generate_ceo_report():
    """Generate daily CEO report with Fibonacci status."""

    scaler = FibonacciScaler(paper=True)
    fib_result = scaler.calculate_daily_investment()

    report = f"""
    DAILY TRADING REPORT
    Date: {datetime.now().strftime('%Y-%m-%d')}

    FIBONACCI SCALING STATUS
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━
    Current Level: ${fib_result['current_level']:.0f}/day
    Daily Investment: ${fib_result['daily_amount']:.2f}
    Cumulative Profit: ${fib_result['cumulative_profit']:.2f}

    Next Milestone: ${fib_result['next_milestone']:.2f}
    Progress: {fib_result['progress_to_next']:.1f}%
    Profit Needed: ${fib_result['profit_to_next_level']:.2f}
    """

    if fib_result.get('scaled_up'):
        report += f"""
    ✨ SCALE-UP EVENT TODAY! ✨
    {fib_result['previous_level']:.0f} → {fib_result['current_level']:.0f}/day
    """

    if fib_result.get('at_max_level'):
        report += f"""
    🏁 AT MAXIMUM LEVEL ($100/day)
    """

    return report
```

---

## State File Locations

### Fibonacci Scaling State
- **Path**: `data/fibonacci_scaling_state.json`
- **Contains**: Current level, scale-up history
- **Auto-created**: Yes (on first run)

### System State (Profit Tracking)
- **Path**: `data/system_state.json`
- **Used for**: Cumulative profit (`account.total_pl`)
- **Updated by**: Trading system

---

## Testing in Isolation

Test without running actual trades:

```python
from scripts.financial_automation import FibonacciScaler

# Initialize
scaler = FibonacciScaler(paper=True)

# Get status
result = scaler.calculate_daily_investment()

# Print details
print(f"Daily Amount: ${result['daily_amount']:.2f}")
print(f"Current Profit: ${result['cumulative_profit']:.2f}")
print(f"Current Level: ${result['current_level']:.0f}/day")
print(f"Next Milestone: ${result['next_milestone']:.2f}")
```

---

## Frequently Asked Questions

### Q: When does the level change?
**A**: When `cumulative_profit >= next_level × 30 days`

Example: To reach $2/day, you need $60 cumulative profit ($2 × 30 = $60)

### Q: What if profit goes negative?
**A**: Level stays at $1/day (minimum). Never goes below base level.

### Q: Can I skip levels?
**A**: No. If you go from $100 profit to $1000 overnight, you still progress through each Fibonacci level ($3 → $5 → $8 → etc.)

### Q: What happens at $100/day?
**A**: This is the maximum. Safety cap prevents over-leverage.

### Q: How do I reset to $1/day?
**A**: Delete `data/fibonacci_scaling_state.json` and restart. Level recalculates from profit.

### Q: Where are scale-up events logged?
**A**:
1. Console (via `logger.info()`)
2. `data/fibonacci_scaling_state.json` (scale_up_history)

---

## Troubleshooting

### Error: "Failed to get account data"
**Cause**: Alpaca API connection issue
**Solution**: Check API keys, network connection

### Fallback mode triggered
**Cause**: Exception in calculation
**Solution**: Check logs, verify system_state.json exists

### Level not changing
**Cause**: Haven't hit milestone yet
**Solution**: Check progress with `result['progress_to_next']`

---

## Migration from Linear Scaling

If currently using `DynamicInvestmentScaler`:

```python
# Old way (deprecated)
from scripts.financial_automation import DynamicInvestmentScaler
scaler = DynamicInvestmentScaler(paper=True)

# New way (recommended)
from scripts.financial_automation import FibonacciScaler
scaler = FibonacciScaler(paper=True)

# Same interface - no other changes needed!
result = scaler.calculate_daily_investment()
daily_amount = result['daily_amount']
```

---

## Quick Reference

| Profit | Daily Amount | Milestone |
|--------|--------------|-----------|
| $0+ | $1 | Base level |
| $60+ | $2 | First scale-up |
| $90+ | $3 | |
| $150+ | $5 | |
| $240+ | $8 | |
| $390+ | $13 | |
| $630+ | $21 | |
| $1,020+ | $34 | |
| $1,650+ | $55 | |
| $2,670+ | $89 | |
| $3,000+ | $100 | Maximum |

---

**Questions?** See `/home/user/trading/docs/fibonacci_scaling.md` for complete documentation.
