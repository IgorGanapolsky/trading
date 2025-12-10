# Anthropic Agent Patterns Implementation

Based on [Anthropic's Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents) guidance.

## Overview

This document describes the Anthropic-recommended patterns implemented in our trading system.

## 1. Human-in-the-Loop Checkpoints

**Location**: `src/agents/anthropic_patterns.py`

### Multi-Dimensional Risk Assessment

Instead of just trade value, we assess risk across multiple dimensions:

| Dimension | Threshold | Risk Level |
|-----------|-----------|------------|
| Trade Value | > $50 | HIGH |
| Daily Loss | > 2% | HIGH |
| Consecutive Losses | ≥ 3 | CRITICAL |
| Volatility Spike | > 2x normal | MEDIUM |
| Position Correlation | > 80% | MEDIUM |

### Risk Levels and Actions

```
LOW      → Auto-approve, log for audit
MEDIUM   → Proceed with warning notification
HIGH     → Pause, request confirmation (5 min timeout)
CRITICAL → Block until explicit CEO approval
```

### Usage

```python
from src.agents.anthropic_patterns import RiskCheckpoint, create_trading_checkpoint

# Create checkpoint for trade
checkpoint = create_trading_checkpoint({
    "trade_value": 75.0,
    "daily_pnl_pct": -0.015,
    "consecutive_losses": 2
})

if checkpoint.requires_human_approval():
    # Wait for CEO decision
    await wait_for_approval(checkpoint.checkpoint_id)
```

## 2. Error Recovery Framework

**Location**: `src/agents/anthropic_patterns.py`

### Fallback Strategies

```
RETRY_SAME      → Retry the same tool with exponential backoff
FALLBACK_TOOL   → Use alternative tool (e.g., cached data)
DEGRADE         → Continue without this capability
ABORT           → Stop the workflow entirely
HUMAN           → Request human intervention
```

### Pre-configured Recovery Paths

| Tool | Max Retries | Fallback | Strategy |
|------|-------------|----------|----------|
| `get_market_data` | 3 | `get_cached_market_data` | FALLBACK_TOOL |
| `analyze_sentiment` | 2 | - | DEGRADE |
| `execute_trade` | 5 | - | HUMAN (critical) |
| `assess_risk` | 2 | `conservative_risk_estimate` | FALLBACK_TOOL |

### Usage

```python
from src.agents.anthropic_patterns import error_recovery

success, result, error = await error_recovery.execute_with_recovery(
    tool_name="get_market_data",
    tool_func=fetch_market_data,
    fallback_funcs={"get_cached_market_data": get_cached_data},
    symbol="NVDA"
)
```

## 3. Evaluator-Optimizer Loop

**Location**: `src/agents/rl_evaluator_optimizer.py`

### Pattern Description

```
┌─────────────────────────────────────────────────┐
│                                                 │
│  ┌──────────┐    ┌───────────┐    ┌──────────┐ │
│  │ Execute  │───▶│ Evaluate  │───▶│ Optimize │ │
│  │ Strategy │    │ Results   │    │ Params   │ │
│  └──────────┘    └───────────┘    └──────────┘ │
│       ▲                                  │      │
│       └──────────────────────────────────┘      │
│                  (loop until pass)              │
└─────────────────────────────────────────────────┘
```

### Phase-Specific Goals

| Phase | Win Rate | Sharpe | Max DD | Daily Profit |
|-------|----------|--------|--------|--------------|
| Month 1 | 45%+ | 0.0+ | 15% | -$5 (ok) |
| Month 2 | 55%+ | 1.0+ | 10% | $0 |
| Month 3 | 60%+ | 1.5+ | 8% | $3+ |

### Usage

```python
from src.agents.rl_evaluator_optimizer import optimize_rl_strategy

# Run optimization loop
optimized_params, final_eval = await optimize_rl_strategy(
    phase=2,  # Month 2
    max_iterations=10
)

if final_eval.passed:
    print("Strategy validated!")
else:
    print(f"Suggestions: {final_eval.suggestions}")
```

## 4. Action-Oriented Tool Design

### Bad (Data Getters)
```
get_positions()
list_orders()
get_account()
get_market_data()
```

### Good (Action Verbs)
```
assess_portfolio_risk()    # Returns positions + risk analysis
execute_trade()            # Places order with validation
validate_trading_capacity() # Checks if trade is feasible
analyze_market_conditions() # Returns actionable signals
```

### Tool Design Checklist

- [ ] Name starts with action verb (execute, assess, validate, analyze)
- [ ] Description explains the ACTION, not just data returned
- [ ] Side effects are documented
- [ ] Reversibility is noted
- [ ] Approval requirements are specified

## Integration with Trade Gateway

**Location**: `src/agents/gateway_integration.py`

### Enhanced Flow

```
1. AI requests trade
   │
2. Original Gateway evaluates (existing logic)
   │
3. If approved → Multi-dimensional risk checkpoint
   │
4. If HIGH/CRITICAL risk → Human approval required
   │
5. Execute with error recovery framework
```

### Usage

```python
from src.agents.gateway_integration import get_enhanced_gateway

# Create enhanced gateway
gateway = get_enhanced_gateway()

# Evaluate with checkpoint
decision = await gateway.evaluate_with_checkpoint(
    request,
    context={"consecutive_losses": 2}
)

if decision.requires_human_approval:
    approved, reason = await gateway.wait_for_approval(
        decision.checkpoint.checkpoint_id
    )
    if not approved:
        return  # Trade blocked

# Execute with recovery
result = await gateway.execute_with_recovery(decision, execute_trade)
```

## References

- [Anthropic: Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)
- [Anthropic: Writing Tools for Agents](https://www.anthropic.com/engineering/writing-tools-for-agents)
- [Docker: Multi-Agent Systems](https://www.docker.com/blog/how-to-build-a-multi-agent-system/)
