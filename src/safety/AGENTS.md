# Safety Module - Agent Instructions

> Risk management, circuit breakers, and trade validation.

## Purpose

This module is the **guardian** of the trading system:
- Validates all trades before execution
- Enforces position limits and risk budgets
- Triggers circuit breakers on anomalies
- Prevents catastrophic losses

## CRITICAL: NEVER BYPASS

**All changes to this module require EXTRA scrutiny.**
A bug here can cause real financial loss.

## Risk Limits (HARDCODED)

| Rule | Value | File |
|------|-------|------|
| Max risk per trade | 2% | `risk_manager.py` |
| Max position size | 5% | `position_sizer.py` |
| Max concurrent positions | 5 | `portfolio_limits.py` |
| Daily loss limit | 3% | `circuit_breakers.py` |
| Max drawdown | 10% | `circuit_breakers.py` |

## Circuit Breakers

Automatic trading halt conditions:
1. Daily loss exceeds 3%
2. Single trade loss exceeds 2%
3. Win rate drops below 30% (rolling 20 trades)
4. API errors exceed threshold
5. Market volatility spike (VIX > 30)

## Modification Rules

1. **NEVER reduce safety limits** without CEO approval
2. **ALWAYS add tests** for any new validation
3. **NEVER catch and ignore exceptions** - Let them propagate
4. **LOG ALL rejections** with detailed reason

## Good Pattern

```python
def validate_trade(signal: TradeSignal, portfolio: Portfolio) -> ValidationResult:
    """Validate trade against risk rules.

    Returns:
        ValidationResult with status and reason
    """
    # Check position size limit
    if signal.position_value > portfolio.equity * MAX_POSITION_PCT:
        return ValidationResult(
            status="rejected",
            reason=f"Position {signal.position_value} exceeds {MAX_POSITION_PCT*100}% limit"
        )

    # Check sector concentration
    sector_exposure = portfolio.get_sector_exposure(signal.sector)
    if sector_exposure + signal.position_value > MAX_SECTOR_EXPOSURE:
        return ValidationResult(
            status="rejected",
            reason=f"Sector {signal.sector} would exceed concentration limit"
        )

    return ValidationResult(status="approved")
```

## Testing

```bash
# Safety tests are MANDATORY
pytest tests/safety/ -v

# Run before any merge
pytest tests/safety/test_circuit_breakers.py -v
pytest tests/safety/test_risk_limits.py -v
```

## Related Modules

- `src/strategies/` - Consumes validation results
- `src/orchestrator/` - Calls risk checks before execution
- `rag_knowledge/lessons_learned/` - Past safety incidents
