# Orchestrator Module - Agent Instructions

> Entry point for the trading system. Coordinates all trading operations.

## Purpose

The orchestrator is the **main entry point** for daily trading operations:
- Initializes all subsystems (Alpaca client, strategies, risk manager)
- Coordinates market data fetching
- Executes trading strategies in sequence
- Enforces risk management rules
- Logs all operations

## Key File

`main.py` - Contains `TradingOrchestrator` class

## Critical Import Test

```bash
# ALWAYS verify before merge
python3 -c "from src.orchestrator.main import TradingOrchestrator; print('OK')"
```

If this fails, the ENTIRE trading system is broken.

## Architecture

```
TradingOrchestrator
├── AlpacaClient (broker connection)
├── StrategyManager (strategy execution)
├── RiskManager (safety checks)
├── StateManager (persistence)
└── Logger (audit trail)
```

## Modification Rules

1. **NEVER break the import** - Test after every change
2. **NEVER bypass risk checks** - All trades go through RiskManager
3. **ALWAYS log operations** - Full audit trail required
4. **Type hints required** - Every function must be typed

## Common Tasks

| Task | Where |
|------|-------|
| Add new strategy | `src/strategies/`, then register in orchestrator |
| Modify trade execution | `execute_trade()` method |
| Change risk parameters | `src/safety/risk_manager.py` |
| Update market data | `fetch_market_data()` method |

## Testing

```bash
pytest tests/unit/test_orchestrator.py -v
pytest tests/integration/test_trading_flow.py -v
```
