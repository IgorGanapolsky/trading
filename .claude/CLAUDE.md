# AI Trading System

CTO: Claude | CEO: Igor Ganapolsky

## Strategy (Updated Jan 22, 2026 - NEW $30K ACCOUNT)
- **North Star**: $6,000/month after-tax = FINANCIAL INDEPENDENCE - CEO MANDATE
- **Why revised**: TastyTrade credit spread 11-year backtest showed LOSSES (-7% to -93%). Iron condors from $100K account showed 86% win rate with 1.5:1 reward/risk.
- **Current capital**: $30,000 | Fresh start - clean slate Jan 22, 2026

## Four Pillars of Wealth Building (Phil Town Aligned)
### 1. Capital Preservation (Rule #1: Don't Lose Money)
- NEVER risk more than 5% per trade ($1,500 max)
- Iron condors = defined risk on BOTH sides
- Stop-loss at 200% of credit - NO EXCEPTIONS
- Exit at 7 DTE to avoid gamma risk

### 2. Compounding (Let Money Work for You)
- Reinvest ALL profits back into trading capital
- Target 2-3% monthly returns (24-36% annually)
- Small consistent gains > big risky bets
- $30K → $350K in ~4 years at 25% annual compound

### 3. Reinvestment Strategy
- 100% of trading profits stay in account until $350K reached
- No withdrawals during accumulation phase
- Scale position size as account grows (maintain 5% rule)
- Add external capital when possible to accelerate

### 4. Tax Optimization (CRITICAL - LL-295)
- **SPX/XSP vs SPY**: SPX options get 60/40 tax treatment (Section 1256)
  - SPY: 100% short-term gains (32% tax bracket = 32%)
  - SPX: 60% long-term + 40% short-term = ~22.4% effective rate
  - **Saves ~30% on tax bill** = $15-20K extra over 7 years
- **XSP (Mini-SPX)**: Same tax benefits as SPX at SPY-like prices
  - ⚠️ **ALPACA LIMITATION**: Alpaca does NOT support index options (SPX/XSP)
  - Current strategy uses SPY (equity options) until broker switch
  - Future: Consider TastyTrade or IBKR for Section 1256 benefits
- Track ALL trades for Schedule D / Form 6781 reporting
- Consider tax-loss harvesting on losing positions
- Target: $8,600/month pre-tax = $6,000/month after-tax
- **Primary strategy**: IRON CONDORS on SPY ONLY - defined risk on BOTH sides
- **Iron condor setup**:
  - Sell 15-20 delta put spread (bull put)
  - Sell 15-20 delta call spread (bear call)
  - $5-wide wings, 30-45 DTE
  - Collect premium from BOTH sides
- **CRITICAL MATH**: 15-delta = 86% win rate (LL-220). Risk/reward ~1.5:1 (BETTER than credit spreads)
- **Expiration**: 30-45 DTE, close at 50% max profit OR 7 DTE (whichever first) - LL-268 research
- **Position limit**: 1 iron condor at a time (5% max = $1,500 risk)
- **Monthly target**: 3-4 iron condors x $150-250 avg x 86% win rate = $400-860/month (conservative)
- **Stop-loss**: Close if one side reaches 200% of credit - MANDATORY
- **Adjustment**: If tested, roll untested side closer for additional credit
- **Assignment risk**: Close positions at 7 DTE to avoid gamma risk (changed from 21 DTE per LL-268)
- **Risk management**: NEVER more than 5% on single trade. NO NAKED OPTIONS.
- **Paper phase**: 90 days to validate 80%+ win rate before scaling
- **Why iron condors beat credit spreads**: Collect premium from BOTH sides, better win rate, profit in range-bound markets
- **PDT NOTE**: $30K > $25K = NO PDT RESTRICTIONS (can day trade freely)

## Path to Financial Independence ($6K/month After Tax)
| Year | Capital | Monthly Pre-Tax | After-Tax | Status |
|------|---------|-----------------|-----------|--------|
| Now | $30,000 | $600-900 | ~$420-630 | **Building foundation** |
| Year 1 | $50,000 | $1,000-1,500 | ~$700-1,050 | Compounding |
| Year 2 | $100,000 | $2,000-3,000 | ~$1,400-2,100 | Growing |
| Year 3 | $200,000 | $4,000-6,000 | ~$2,800-4,200 | Scaling |
| Year 4 | $350,000+ | $8,600+ | **$6,000+** | **FINANCIAL INDEPENDENCE** |

**Math**: $350K × 2.5% monthly = $8,750/month pre-tax = ~$6,125/month after 30% tax

**Note**: $30K > $25K = NO PDT RESTRICTIONS. Patience + discipline = freedom.

## MANDATORY Pre-Trade Checklist
1. [ ] Is ticker SPY? (SPY ONLY - best liquidity, tightest spreads)
2. [ ] Is position size ≤5% of account ($1,500)?
3. [ ] Is it an IRON CONDOR (4-leg, defined risk on BOTH sides)?
4. [ ] Are short strikes at 15-20 delta?
5. [ ] 30-45 DTE expiration?
6. [ ] Stop-loss at 200% of credit defined?
7. [ ] Exit plan at 50% profit or 7 DTE? (LL-268: 7 DTE for 80%+ win rate)

## Win Rate Tracking (Data-Driven)
- Track every paper trade: entry, exit, P/L, win/loss
- Required metrics: win rate %, avg win, avg loss, profit factor
- Scale decisions based on REAL data, not projections
- **CRITICAL**: Iron condors at 15-delta = 86% win rate. Target = 80%+ maintained.
- If win rate <80% after 30 trades: check delta selection, may need wider wings
- If win rate 80-85%: on track, maintain discipline
- If win rate 85%+: profitable, consider scaling after 90 days

### Ticker Selection (Jan 19, 2026 - Simplified)
| Priority | Ticker | Rationale |
|----------|--------|-----------|
| 1 | SPY | ONLY ticker. Best liquidity, tightest spreads, no early assignment risk |

**NO individual stocks.** The $100K success was SPY. The $5K failure was SOFI. Learn the lesson.

### Phil Town Alignment Note
Iron condors ALIGN with Rule #1 better than credit spreads:
- Defined risk on BOTH sides (put AND call spread)
- 15-delta = ~85% probability of profit
- 1.5:1 reward/risk ratio (BETTER than credit spreads' 0.5:1)
- Profit if SPY stays within range (most of the time)

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


## Trade Data Architecture (CANONICAL - Jan 17, 2026)

**SINGLE SOURCE OF TRUTH: `data/system_state.json -> trade_history`**

```
┌─────────────────┐    ┌──────────────────────┐    ┌─────────────────────┐
│  Alpaca API     │───>│ sync-system-state.yml│───>│ system_state.json   │
│  (broker)       │    │ (GitHub Actions)     │    │   └─ trade_history  │
└─────────────────┘    └──────────────────────┘    └──────────┬──────────┘
                                                              │
                       ┌──────────────────────┐               │
                       │   trade_sync.py      │───────────────┤
                       │   (local/manual)     │               │
                       └──────────────────────┘               │
                                                              v
                       ┌──────────────────────┐    ┌─────────────────────┐
                       │ Dialogflow Webhook   │<───│ GitHub API (fetch)  │
                       │ (Cloud Run)          │    │ OR local file read  │
                       └──────────────────────┘    └─────────────────────┘
```

### Why This Matters
- **Cloud Run has no local files** - webhook MUST fetch from GitHub API
- **Alpaca is source of truth** - workflow syncs real broker data
- **LL-230**: Previous bug where webhook looked for `trades_*.json` (didn't exist on Cloud Run)

### Files
| File | Purpose | Written By |
|------|---------|------------|
| `data/system_state.json` | **CANONICAL** trade data | sync-system-state.yml, trade_sync.py |
| `data/trades_*.json` | **DEPRECATED** | Legacy, do not use |

See `docs/ARCHITECTURE.md` for detailed architecture documentation.

### Monitoring
- CI workflow `webhook-integration-test.yml` validates `trades_loaded > 0` after every deployment
- Failure = data source mismatch, see LL-230
## What NOT To Do
- Don't create unnecessary documentation
- Don't over-engineer
- Don't document failures - just fix them and learn in RAG

## Context
Hooks provide: portfolio status, market hours, trade count, date verification.
Trust the hooks. They work.

## $30K Paper Account (Jan 22, 2026)
Account ID: PA3PYE0C9MN - Fresh start with no positions.
Use `ALPACA_PAPER_TRADING_5K_API_KEY` (now points to $30K account).
All code must use `get_alpaca_credentials()` from `src/utils/alpaca_client.py`.
**NO PDT RESTRICTIONS** - Can freely close positions same-day.
