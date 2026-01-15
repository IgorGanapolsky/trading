# AI Trading System

CTO: Claude | CEO: Igor Ganapolsky

## Strategy (Updated Jan 15, 2026 - DEEP RESEARCH REVISION v2)
- **North Star**: $150-200/month (3-4% monthly) - MATH VALIDATED
- **Why revised**: Deep research reveals $5 spreads require 88% win rate (unsustainable). Switch to $3 spreads = 70% break-even.
- **Current capital**: $4,989.69 | P/L: -$10.31 (-0.21%) | Portfolio validated by research.
- **Primary strategy**: CREDIT SPREADS on **IWM** (preferred) / SPY - defined risk only
- **Spread setup**: Sell 20-delta put, buy 13-delta put = **$3 wide** = ~$300 collateral, ~$90 premium
- **CRITICAL MATH**: Risk $210 to make $90 = 2.3:1 ratio. Break-even win rate = **70%** ✓
- **Expiration**: 35-45 DTE, close at 50% max profit (improves win rate to 80-85%)
- **Time exits**: Close at 21 DTE OR 7 DTE hard stop (avoid gamma risk) - NEW
- **Delta monitoring**: Close if short strike reaches 40 delta (too close to ATM) - NEW
- **Position limit**: 1 spread at a time (5% max = $249 risk)
- **Monthly target**: 4-6 spreads x $90 x 80% win rate = $150-200/month (achievable)
- **Stop-loss**: Close at 2x credit received ($180 max loss) - MANDATORY
- **Rolling**: If thesis intact and not at stop-loss, roll "down and out" for credit
- **Assignment risk**: Close positions MANUALLY at 7 DTE (hard rule)
- **Risk management**: NEVER more than 5% on single trade. NO NAKED PUTS.
- **Paper phase**: 90 days to validate 80%+ win rate before scaling
- **Market preference**: IWM > SPY (higher IV = better premiums, +6.2% YTD momentum)
- **Research validated**: 100+ sources, industry consensus on parameters

## Recovery Path (Math-Validated Jan 15, 2026)
| Phase | Capital | Monthly Income | Daily Equivalent | Timeline |
|-------|---------|----------------|------------------|----------|
| Now | $4,959 | $150-200 | **$5-10/day** | Immediate |
| +6mo | $9,500 | $285-380 | $14-19/day | With deposits |
| +12mo | $16,000 | $480-640 | $24-32/day | Compounding |
| +24mo | $33,000 | $990-1,320 | $50-66/day | On track |
| +30mo | $45,000 | $1,350-1,800 | **$68-90/day** | Near goal |
| Goal | $50,000+ | $2,000+ | **$100/day** | ~2.5-3 years |

## MANDATORY Pre-Trade Checklist (Updated Jan 15, 2026)
1. [ ] Is ticker **IWM** (preferred) or SPY? (NO other tickers)
2. [ ] Is spread width **$3** (not $5 or $10)?
3. [ ] Is position size ≤5% of account ($249)?
4. [ ] Is it a SPREAD (not naked put)?
5. [ ] VIX < 18? (avoid high volatility entry)
6. [ ] 35-45 DTE expiration?
7. [ ] Stop-loss at 2x credit? ($180 max loss for $90 credit)
8. [ ] Profit target at 50% max gain? ($45 buyback for $90 credit)
9. [ ] Time exit at 21 DTE scheduled?
10. [ ] Hard stop at 7 DTE scheduled?

## Win Rate Tracking (Data-Driven - Updated Jan 15, 2026)
- Track every paper trade: entry, exit, P/L, win/loss
- **Required metrics**: win rate %, avg win, avg loss, **profit factor** (must be >1.5)
- Scale decisions based on REAL data, not projections
- **CRITICAL**: Break-even win rate = **70%** (with $3 spreads). Target = **80%+** with early exits.
- **Profit Factor Formula**: (Total Win $ ÷ Total Loss $) - must be ≥1.5 to be profitable
- If win rate <70% after 30 trades: strategy broken (below break-even)
- If win rate 70-75%: break-even to marginal (need improvement)
- If win rate 75-80%: profitable, proceed with caution
- If win rate 80%+: excellent, consider scaling after 90 days
- **Industry data**: 20-delta strikes = ~80% actual win rate (validated)

### Ticker Hierarchy (Jan 15, 2026 Deep Research Update)
| Priority | Ticker | Rationale | IV | YTD | Blackout |
|----------|--------|-----------|----|----|----------|
| 1 | **IWM** | **PREFERRED** - Higher IV (19-20%), +6.2% YTD, rate cut tailwinds | ~19% | +6.2% | None |
| 2 | SPY | Good liquidity but lower premiums, mixed 2026 outlook | ~13% | +1.8% | None |
| 3 | ~~F~~ | REMOVED - individual stock risk violates core strategy | - | - | - |
| 4 | ~~T~~ | REMOVED - individual stock risk violates core strategy | - | - | - |
| 5 | ~~SOFI~~ | REMOVED - individual stock risk violates core strategy | - | - | - |

**Research Finding**: Focus ONLY on IWM/SPY. Individual stocks add unnecessary risk and lower win rates.

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
