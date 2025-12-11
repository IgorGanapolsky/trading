# Strategies Module - Agent Instructions

> Trading strategy implementations for different market conditions.

## Purpose

Contains all trading strategy logic:
- Signal generation based on technical/fundamental analysis
- Entry and exit rules
- Position sizing recommendations
- Strategy-specific parameters

## Strategy Tiers

| Tier | Strategy | Risk | Allocation |
|------|----------|------|------------|
| 1 | Core ETFs (SPY, QQQ) | Low | 40% |
| 2 | Growth Stocks | Medium | 30% |
| 3 | Momentum | Medium-High | 20% |
| 4 | Mean Reversion | Medium | 10% |

## Key Patterns

### Strategy Interface

All strategies must implement:

```python
from abc import ABC, abstractmethod
from typing import Optional
from src.models.signal import TradeSignal
from src.models.market_data import MarketData

class BaseStrategy(ABC):
    """Base class for all trading strategies."""

    @abstractmethod
    def generate_signal(self, market_data: MarketData) -> Optional[TradeSignal]:
        """Generate trading signal from market data.

        Args:
            market_data: Current market data snapshot

        Returns:
            TradeSignal if opportunity found, None otherwise
        """
        pass

    @abstractmethod
    def get_parameters(self) -> dict:
        """Return strategy parameters for logging."""
        pass
```

### Adding a New Strategy

1. Create file: `src/strategies/my_strategy.py`
2. Implement `BaseStrategy` interface
3. Add tests: `tests/unit/strategies/test_my_strategy.py`
4. Register in orchestrator
5. Add to strategy tier documentation

## Backtest Requirements

Before deploying any strategy:
1. Minimum 1 year historical backtest
2. Sharpe ratio > 1.0
3. Maximum drawdown < 15%
4. Win rate > 50%
5. Document in `docs/backtest_results/`

## Common Pitfalls

- **Overfitting**: Optimize on out-of-sample data
- **Look-ahead bias**: Never use future data in signals
- **Survivorship bias**: Include delisted stocks in backtests
- **Ignoring costs**: Account for spreads and commissions

## Testing

```bash
pytest tests/unit/strategies/ -v
pytest tests/backtesting/ -v
```

## Related

- `src/backtesting/` - Backtest framework
- `src/ml/` - ML-based signal generation
- `data/backtest_results/` - Historical performance
