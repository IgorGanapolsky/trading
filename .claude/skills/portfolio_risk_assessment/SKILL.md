---
skill_id: portfolio_risk_assessment
name: Portfolio Risk Assessment
version: 1.0.0
description: Comprehensive portfolio health monitoring, circuit breakers, and trade validation for risk management
author: Trading System CTO
tags: [risk-management, trading, safety, circuit-breakers]
tools:
  - assess_portfolio_health
  - check_circuit_breakers
  - validate_trade
  - record_trade_result
dependencies:
  - alpaca-py
  - python-dotenv
integrations:
  - src/core/risk_manager.py
---

# Portfolio Risk Assessment Skill

Safety-critical skill for managing trading risk and preventing catastrophic losses.

## Overview

This skill provides:
- Real-time portfolio health assessment
- Circuit breaker monitoring and enforcement
- Pre-trade validation
- Post-trade result recording
- Risk metrics calculation

## Circuit Breakers (Automatic Trading Halt)

The system implements multiple circuit breakers:

1. **Daily Loss Limit**: Halt trading if daily loss exceeds 2% of account value
2. **Maximum Drawdown**: Halt if total drawdown exceeds 10%
3. **Consecutive Losses**: Halt after 3 consecutive losing trades
4. **Volatility Spike**: Halt if market volatility exceeds 3x normal
5. **Anomaly Score**: Halt if trading anomalies detected

## Tools

### 1. assess_portfolio_health

Comprehensive health check of current portfolio.

**Parameters:**
- None (uses current account state)

**Returns:**
```json
{
  "success": true,
  "data": {
    "overall_status": "HEALTHY",
    "account_equity": 100000.50,
    "total_pl": 150.25,
    "total_pl_pct": 0.15,
    "daily_pl": 25.50,
    "daily_pl_pct": 0.03,
    "max_drawdown": 2.5,
    "current_drawdown": 0.5,
    "position_count": 3,
    "cash_percentage": 85.0,
    "buying_power": 199500.00,
    "risk_score": 2.5,
    "warnings": []
  }
}
```

**Health Status Levels:**
- `HEALTHY`: All metrics within safe ranges
- `CAUTION`: Approaching risk limits (yellow flag)
- `WARNING`: Risk limits being tested (orange flag)
- `CRITICAL`: Circuit breakers may trigger (red flag)
- `HALTED`: Trading automatically stopped

### 2. check_circuit_breakers

Checks if any circuit breakers should trigger.

**Parameters:**
- `force_check` (optional): Force re-evaluation even if recently checked

**Returns:**
```json
{
  "success": true,
  "data": {
    "should_halt_trading": false,
    "active_breakers": [],
    "warning_breakers": ["daily_loss_approaching"],
    "breaker_status": {
      "daily_loss": {
        "triggered": false,
        "current_value": -1.5,
        "threshold": -2.0,
        "pct_to_threshold": 75.0
      },
      "max_drawdown": {
        "triggered": false,
        "current_value": 3.5,
        "threshold": 10.0,
        "pct_to_threshold": 35.0
      },
      "consecutive_losses": {
        "triggered": false,
        "current_value": 1,
        "threshold": 3,
        "pct_to_threshold": 33.3
      }
    }
  }
}
```

### 3. validate_trade

Validates a proposed trade against risk management rules.

**Parameters:**
- `symbol` (required): Ticker symbol
- `side` (required): "buy" or "sell"
- `quantity` (required): Number of shares (can be fractional)
- `order_type` (required): "market", "limit", "stop", "stop_limit"
- `limit_price` (optional): Limit price for limit orders
- `stop_price` (optional): Stop price for stop orders

**Returns:**
```json
{
  "success": true,
  "data": {
    "is_valid": true,
    "trade_approved": true,
    "estimated_cost": 150.25,
    "estimated_risk": 3.50,
    "position_size_pct": 0.15,
    "warnings": [],
    "recommendations": [
      "Consider reducing position size to 0.10% of portfolio"
    ],
    "validation_checks": {
      "sufficient_buying_power": true,
      "within_position_limits": true,
      "within_daily_trade_limit": true,
      "passes_risk_limits": true,
      "no_active_circuit_breakers": true
    }
  }
}
```

**Validation Failures:**
```json
{
  "success": true,
  "data": {
    "is_valid": false,
    "trade_approved": false,
    "rejection_reasons": [
      "Circuit breaker active: daily_loss_limit",
      "Insufficient buying power: need $1000, have $500"
    ]
  }
}
```

### 4. record_trade_result

Records the outcome of a completed trade for risk tracking.

**Parameters:**
- `trade_id` (required): Unique trade identifier
- `symbol` (required): Ticker symbol
- `side` (required): "buy" or "sell"
- `quantity` (required): Shares traded
- `entry_price` (required): Fill price
- `exit_price` (optional): Exit price if closed
- `profit_loss` (optional): Realized P/L
- `status` (required): "filled", "partial", "cancelled", "rejected"

**Returns:**
```json
{
  "success": true,
  "data": {
    "recorded": true,
    "trade_id": "abc123",
    "consecutive_wins": 2,
    "consecutive_losses": 0,
    "updated_metrics": {
      "total_trades": 45,
      "winning_trades": 28,
      "win_rate": 62.2
    }
  }
}
```

## Integration with Risk Manager

This skill wraps and extends the existing `src/core/risk_manager.py`:

```python
from claude_skills import load_skill

risk_skill = load_skill("portfolio_risk_assessment")

# Check health before trading
health = risk_skill.assess_portfolio_health()
if health["data"]["overall_status"] != "HEALTHY":
    print(f"Warning: Portfolio status is {health['data']['overall_status']}")

# Validate trade
validation = risk_skill.validate_trade(
    symbol="AAPL",
    side="buy",
    quantity=0.5,
    order_type="market"
)

if validation["data"]["trade_approved"]:
    # Execute trade
    pass
else:
    print("Trade rejected:", validation["data"]["rejection_reasons"])
```

## Safety Features

1. **Automatic Halting**: System automatically stops trading when circuit breakers trigger
2. **Pre-Trade Validation**: Every trade validated before execution
3. **Real-Time Monitoring**: Continuous health assessment
4. **Audit Trail**: All decisions logged for compliance
5. **Fail-Safe Defaults**: System errs on the side of caution

## Alert Thresholds

| Metric | Caution | Warning | Critical |
|--------|---------|---------|----------|
| Daily Loss | -1.0% | -1.5% | -2.0% |
| Drawdown | 5% | 7.5% | 10% |
| Consecutive Losses | 2 | 3 | 4 |
| Position Size | 8% | 10% | 12% |
| Portfolio Heat | 4% | 5% | 6% |

## Usage in Trading Loop

```python
# Daily trading routine
while market_open:
    # 1. Check circuit breakers
    breakers = risk_skill.check_circuit_breakers()
    if breakers["data"]["should_halt_trading"]:
        print("Trading halted by circuit breakers")
        break

    # 2. Assess portfolio health
    health = risk_skill.assess_portfolio_health()
    print(f"Portfolio status: {health['data']['overall_status']}")

    # 3. Generate signals (from RL agent)
    signal = rl_agent.get_signal()

    # 4. Validate trade
    validation = risk_skill.validate_trade(**signal)

    # 5. Execute if approved
    if validation["data"]["trade_approved"]:
        result = execute_trade(signal)

        # 6. Record result
        risk_skill.record_trade_result(**result)
```

## CLI Usage

```bash
# Check portfolio health
python scripts/risk_assessment.py assess_portfolio_health

# Check circuit breakers
python scripts/risk_assessment.py check_circuit_breakers

# Validate a trade
python scripts/risk_assessment.py validate_trade \
    --symbol AAPL \
    --side buy \
    --quantity 0.5 \
    --order-type market
```
