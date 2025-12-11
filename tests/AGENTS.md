# Tests - Agent Instructions

> Test suites for verifying trading system correctness.

## Purpose

Tests are **specifications** for the trading system:
- Define expected behavior
- Catch regressions before production
- Document edge cases
- Enable confident refactoring

## Test Organization

```
tests/
├── unit/              # Fast, isolated tests (~30s total)
│   ├── strategies/
│   ├── safety/
│   ├── ml/
│   └── utils/
├── safety/            # Safety-critical tests (MANDATORY)
├── integration/       # Multi-component tests
├── e2e/               # Full system tests (slow)
├── backtesting/       # Strategy backtests
└── fixtures/          # Shared test data
```

## Running Tests

```bash
# Fast unit tests (run frequently)
pytest tests/unit -v

# Safety tests (MANDATORY before merge)
pytest tests/safety -v

# All except E2E
pytest tests/ -v --ignore=tests/e2e

# With coverage
pytest tests/unit --cov=src --cov-report=term-missing
```

## Test Naming Convention

Use BDD-style names that explain the scenario:

```python
# Good - explains the scenario
def test_position_sizer_rejects_trade_when_risk_exceeds_2_percent():
    pass

def test_circuit_breaker_halts_trading_after_3_percent_daily_loss():
    pass

# Bad - unclear what's being tested
def test_position_sizer():
    pass

def test_circuit_breaker():
    pass
```

## Test Structure (AAA Pattern)

```python
def test_momentum_strategy_generates_buy_signal_on_breakout():
    """
    GIVEN a stock breaking above 20-day high
    WHEN momentum strategy analyzes the data
    THEN it should generate a BUY signal
    """
    # Arrange
    market_data = create_breakout_scenario()
    strategy = MomentumStrategy()

    # Act
    signal = strategy.generate_signal(market_data)

    # Assert
    assert signal is not None
    assert signal.action == "buy"
    assert signal.confidence > 0.7
```

## Fixtures

Store test data in `tests/fixtures/`:

```python
# tests/conftest.py
import pytest
import json
from pathlib import Path

@pytest.fixture
def sample_portfolio():
    """Load sample portfolio for testing."""
    fixture_path = Path(__file__).parent / "fixtures" / "sample_portfolio.json"
    return json.loads(fixture_path.read_text())

@pytest.fixture
def mock_alpaca_client():
    """Create mocked Alpaca client."""
    from unittest.mock import MagicMock
    client = MagicMock()
    client.get_account.return_value = {"equity": 10000}
    return client
```

## Safety Tests (CRITICAL)

These tests MUST pass before any merge:

```bash
# Circuit breaker tests
pytest tests/safety/test_circuit_breakers.py -v

# Risk limit tests
pytest tests/safety/test_risk_limits.py -v

# Position sizing tests
pytest tests/safety/test_position_sizing.py -v
```

## When to Add Tests

1. **Every new feature** - Write test first (TDD)
2. **Every bug fix** - Add test that would have caught it
3. **Every edge case** - Document in test
4. **Every lesson learned** - Prevent regression

## Common Patterns

### Testing Exceptions

```python
import pytest

def test_risk_manager_raises_on_invalid_stop_loss():
    """Risk manager should reject invalid stop loss."""
    with pytest.raises(ValueError, match="Stop loss must be below entry"):
        calculate_position_size(
            equity=10000,
            risk_percent=0.02,
            entry_price=150,
            stop_loss=160  # Invalid: above entry
        )
```

### Testing Async Code

```python
import pytest

@pytest.mark.asyncio
async def test_alpaca_client_fetches_positions():
    """Alpaca client should return current positions."""
    client = AlpacaClient()
    positions = await client.get_positions()

    assert isinstance(positions, list)
```

### Parametrized Tests

```python
import pytest

@pytest.mark.parametrize("equity,risk,expected", [
    (10000, 0.01, 100),   # 1% of $10k = $100 risk
    (10000, 0.02, 200),   # 2% of $10k = $200 risk
    (50000, 0.02, 1000),  # 2% of $50k = $1000 risk
])
def test_risk_calculation(equity, risk, expected):
    """Risk calculation should scale with equity and risk percent."""
    result = calculate_max_risk(equity, risk)
    assert result == expected
```

## CI Integration

Tests run automatically on:
- Every push
- Every PR
- Before merge (pre_merge_gate.py)

Merge is BLOCKED if any test fails.
