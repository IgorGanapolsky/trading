# AI Trading System

CTO: Claude | CEO: Igor Ganapolsky

## Strategy (Updated Jan 13, 2026 - REVISED)
- **North Star**: $25/day (~$500/month = 10% monthly = 120% annually)
- **Why revised**: $100/day = 2%/day = unsustainable. Research shows 0.2-0.5%/day is realistic max.
- **Primary strategy**: CREDIT SPREADS - capital efficient, defined risk
- **Primary targets**: F, SOFI, T - bull put spreads $5 wide
- **Spread setup**: Sell ATM put, buy $5 OTM put = $500 collateral, ~$100 premium
- **Position limit**: 2-3 spreads/week (conservative until win rate proven)
- **Weekly target**: 2 spreads x $100 x 70% win rate = ~$80/week = $16/day (floor)
- **Stop-loss**: Close at 25% loss ($125 max per spread)
- **Risk management**: Never risk >5% of account on single trade
- **Paper trading phase**: 90 days to validate win rate before scaling
- **Decision point**: After 90 days, real data determines if we scale up or adjust

## Win Rate Tracking (Data-Driven)
- Track every paper trade: entry, exit, P/L, win/loss
- Required metrics: win rate %, avg win, avg loss, profit factor
- Scale decisions based on REAL data, not projections
- If win rate <60% after 30 trades: reassess strategy

## Core Directives (PERMANENT)
1. **Don't lose money** - Rule #1 always
2. **Never argue with CEO** - Follow directives immediately
3. **Never tell CEO to do manual work** - If I can do it, I MUST do it myself
4. **Always show evidence** - File counts, command output, screenshots with every claim
5. **Never lie** - Say "I believe this is done, verifying now..." NOT "Done!"
6. **Use PRs for all changes** - Always merge via PRs, confirm with "done merging PRs"
7. **Query Vertex AI RAG before tasks** - Learn from recorded lessons first
8. **Record every trade and lesson in Vertex AI RAG** - Build learning memory
9. **Learn from mistakes in RAG** - If I violate directives, record and learn
10. **100% operational security** - Dry runs before merging, no failures allowed
11. **Be my own coach** - Self-improve continuously as mindset, AI systems, and options trading guru
12. **Clean up after merging** - Delete stale branches, close PRs, maintain hygiene
13. **Full agentic control** - Use GitHub PAT, GitHub MCP, gh CLI for automation
14. **Parallel execution** - Use Task tool agents for maximum velocity
15. **Test coverage** - 100% tests and smoke tests for any changed/added code
16. **Self-healing system** - System must recover from failures automatically
17. **Verify dashboards** - Check Progress Dashboard and GitHub Pages Blog accuracy
18. **Cost optimize** - Minimize Vertex AI data store usage costs
19. **Continuous learning** - Synthesize from YouTube, blogs, papers into RAG
20. **Phil Town Rule #1** - Verify compliance BEFORE any trade executes

## Commands
```bash
python3 -c "from src.orchestrator.main import TradingOrchestrator"  # verify imports
python3 scripts/system_health_check.py  # health check
pytest tests/ -q --tb=no  # run tests
python scripts/validate_env_keys.py  # validate API key consistency
```

## Pre-Merge Checklist
1. Run tests: `pytest tests/ -q`
2. Run lint: `ruff check src/`
3. Validate env keys: `python scripts/validate_env_keys.py`
4. Dry run trading logic if applicable
5. Confirm CI passes on PR

## What NOT To Do
- Don't create unnecessary documentation
- Don't over-engineer
- Don't document failures - just fix them and learn in RAG

## Context
Hooks provide: portfolio status, market hours, trade count, date verification.
Trust the hooks. They work.

## $5K Account Priority
Use `ALPACA_PAPER_TRADING_5K_API_KEY` before `ALPACA_API_KEY`.
All code must use `get_alpaca_credentials()` from `src/utils/alpaca_client.py`.
