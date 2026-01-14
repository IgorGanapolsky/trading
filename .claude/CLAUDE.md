# AI Trading System

CTO: Claude | CEO: Igor Ganapolsky

## Strategy (Updated Jan 14, 2026 - CTO AUTONOMOUS REVISION)
- **North Star**: $14-25/day (~$300-500/month = 6-10% monthly)
- **Why revised**: Research confirms 0.2-0.5%/day max sustainable. VIX at 15 = low IV environment.
- **Primary strategy**: CREDIT SPREADS - capital efficient, defined risk
- **Primary targets**: SPY, IWM first (best liquidity), then F, T (avoid SOFI until Feb 1)
- **Spread setup**: Sell 30-delta put, buy 20-delta put = ~$500 collateral, ~$60-80 premium
- **Why 30-delta**: ATM violates Phil Town Rule #1 (no margin of safety). 30-delta = 70% win rate.
- **Expiration**: 30-45 DTE (sweet spot for theta decay), close at 50% max profit
- **Position limit**: 1 spread at a time initially (5% max risk per trade)
- **Weekly target**: 1 spread x $70 x 70% win rate = ~$50/week = $10/day (floor)
- **Stop-loss**: Close at 2x credit received OR 25% of spread width
- **Risk management**: Max 1-2 concurrent spreads, never >5% account on single trade
- **Paper trading phase**: 90 days to validate win rate before scaling
- **Decision point**: After 30 trades with real data, adjust or continue

## Win Rate Tracking (Data-Driven)
- Track every paper trade: entry, exit, P/L, win/loss
- Required metrics: win rate %, avg win, avg loss, profit factor
- Scale decisions based on REAL data, not projections
- If win rate <60% after 30 trades: reassess strategy

### Ticker Hierarchy (Jan 2026 Research)
| Priority | Ticker | Rationale | Blackout |
|----------|--------|-----------|----------|
| 1 | SPY | Best liquidity, tightest spreads | None |
| 2 | IWM | Small cap exposure, good vol | None |
| 3 | F | Undervalued, 4.2% div support | Feb 3-10 (earnings Feb 10) |
| 4 | T | Stable, low IV = lower premiums | TBD earnings |
| 5 | SOFI | **AVOID until Feb 1** | Jan 23-30 (earnings Jan 30, IV 55%) |

### Phil Town Alignment Note
Credit spreads conflict with Rule #1 (risk $400 to make $100).
Mitigations: Use 30-delta (not ATM) for margin of safety, strict stops, small position sizes.

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
