# AI Trading System

CTO: Claude | CEO: Igor Ganapolsky

## Strategy (Updated Jan 14, 2026 - RESEARCH-BACKED REVISION)
- **North Star**: $150-250/month (3-5% monthly) - RESEARCH VALIDATED
- **Why revised**: Deep research confirms 3-5% monthly is realistic for $5K accounts. 40%/month ($100/day) requires $40K+ capital.
- **Current capital**: $4,959.26 | Loss: -$40.74 (-0.81%) | Lesson paid.
- **Primary strategy**: CREDIT SPREADS on SPY/IWM ONLY - defined risk
- **Spread setup**: Sell 30-delta put, buy 20-delta put = ~$500 collateral, ~$50-70 premium
- **Why 30-delta**: 70% probability of profit. Margin of safety per Phil Town.
- **Expiration**: 30-45 DTE, close at 50% max profit
- **Position limit**: 1 spread at a time (5% max = $248 risk)
- **Monthly target**: 3-4 spreads x $50 x 70% = $105-140/month (realistic)
- **Stop-loss**: Close at 2x credit received OR 25% spread width
- **Risk management**: NEVER more than 5% on single trade. NO NAKED PUTS.
- **Paper phase**: 90 days to validate 70%+ win rate before scaling

## Recovery Path (Research-Based)
| Phase | Capital | Monthly Target | Timeline |
|-------|---------|----------------|----------|
| Now | $4,959 | $150-250 (3-5%) | Immediate |
| +6mo | ~$6,500 | $195-325 | With $25/day deposits |
| +12mo | ~$9,000 | $270-450 | Compounding |
| +24mo | ~$15,000 | $450-750 | On track |
| Goal | $40,000 | $2,000 ($100/day) | 3-4 years realistic |

## MANDATORY Pre-Trade Checklist
1. [ ] Is ticker SPY or IWM? (NO individual stocks until proven)
2. [ ] Is position size ≤5% of account ($248)?
3. [ ] Is it a SPREAD (not naked put)?
4. [ ] Checked earnings calendar? (No blackout violations)
5. [ ] 30-45 DTE expiration?
6. [ ] Stop-loss defined before entry?

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
