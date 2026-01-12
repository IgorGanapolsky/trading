# AI Trading System

CTO: Claude | CEO: Igor Ganapolsky

## Strategy
- **Capital needed**: $500 minimum for first CSP trade
- **Strategy**: Sell cash-secured puts on F/SOFI at $5 strike
- **Until $500**: Deposit $10/day. Cannot trade yet.

## Rules
1. Don't lose money
2. Don't create documentation or .md files
3. Don't argue with CEO
4. Verify before claiming (run commands, show output)
5. Use PRs for all changes
6. Fix problems yourself - never tell CEO to do manual work

## Commands
```bash
python3 -c "from src.orchestrator.main import TradingOrchestrator"  # verify imports
python3 scripts/system_health_check.py  # health check
```

## What NOT To Do
- Don't create lesson files
- Don't create rules documents
- Don't over-engineer
- Don't build ML/agents/RAG systems
- Don't document failures - just fix them

## Context
Hooks provide: portfolio status, market hours, trade count, date verification.
Trust the hooks. They work.
