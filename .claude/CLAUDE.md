# AI Trading System

CTO: Claude | CEO: Igor Ganapolsky

## Strategy (Updated Jan 14, 2026 - INDUSTRY BEST PRACTICE)
- **North Star**: $70-140/month (1.4-2.8% monthly) - INDUSTRY VALIDATED
- **Why revised**: Research shows 92% win rate on SPY 30-delta spreads. 2% position size is industry standard.
- **Current capital**: $4,959.26 | Loss: -$40.74 (-0.81%) | SOFI violation lesson paid.
- **Primary strategy**: CREDIT SPREADS on SPY/IWM ONLY - defined risk
- **Spread setup**: Sell 30-delta put, buy 10-delta put = ~$500 collateral, ~$50-70 premium
- **Why 30-delta**: 70% theoretical, 92% actual backtest win rate. Margin of safety.
- **Expiration**: 45 DTE (optimal theta decay), close at 50% max profit
- **Position limit**: 1 spread at a time (2% max = $100 risk) - INDUSTRY STANDARD
- **Cash reserve**: 50% minimum ($2,500) - for adjustments and black swan protection
- **Monthly target**: 2-3 spreads x $50 x 80% = $80-120/month (conservative)
- **Stop-loss**: Close at 2x credit received
- **Risk management**: NEVER more than 2% on single trade. NO NAKED PUTS. NO BLACKLISTED TICKERS.
- **IV Rank requirement**: Only enter when IV Rank > 30 (currently low)
- **Paper phase**: 90 days to validate 70%+ win rate before scaling

## Recovery Path (Industry-Conservative)
| Phase | Capital | Monthly Target | Risk/Trade |
|-------|---------|----------------|------------|
| Now | $4,959 | $70-140 (1.4-2.8%) | $100 (2%) |
| +6mo | ~$6,500 | $91-182 | $130 (2%) |
| +12mo | ~$9,000 | $126-252 | $180 (2%) |
| +24mo | ~$15,000 | $210-420 | $300 (2%) |
| Goal | $40,000 | $560-1,120 | $800 (2%) |

**Note**: $100/day ($2,000/mo) requires ~$70K capital at 2.8% monthly return.

## MANDATORY Pre-Trade Checklist (STRICT)
1. [ ] Is ticker SPY or IWM? (NO individual stocks - SOFI BANNED)
2. [ ] Is position size ≤2% of account ($100)?
3. [ ] Is it a SPREAD (not naked put)?
4. [ ] Cash reserve ≥50% ($2,500) AFTER this trade?
5. [ ] IV Rank > 30? (skip if low volatility)
6. [ ] 45 DTE expiration?
7. [ ] Stop-loss defined (2x credit received)?
8. [ ] No earnings within 7 days of expiration?

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
