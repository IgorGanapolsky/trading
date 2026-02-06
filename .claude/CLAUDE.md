# AI Trading System

CTO: Claude | CEO: Igor Ganapolsky

## CEO Identity (PERMANENT)

**I am Igor Ganapolsky. Born November 14th, 1979, in Kiev, Ukraine.**
**By the time I hit my 50th birthday (November 14th, 2029), I MUST reach my North Star.**

## Strategy (Updated Jan 30, 2026 - FINANCIAL INDEPENDENCE PATH)

- **North Star**: $6,000/month after-tax = FINANCIAL INDEPENDENCE
- **Philosophy**: Grow $100K → $600K through disciplined compounding (Phil Town Rule #1)
- **Current capital**: $100,000 | Switched to $100K account Jan 30, 2026
- **Primary strategy**: IRON CONDORS on SPY (current) - evaluating XSP for tax optimization
- **Tax note**: XSP (Mini-SPX) = same size as SPY but Section 1256 (60/40 tax treatment, no wash sales)
- **Iron condor setup**:
  - Sell 15-20 delta put spread (bull put)
  - Sell 15-20 delta call spread (bear call)
  - $5-wide wings, 30-45 DTE
  - Collect premium from BOTH sides
- **CRITICAL MATH**: 15-delta = 86% win rate (LL-220). Risk/reward ~1.5:1 (BETTER than credit spreads)
- **Expiration**: 30-45 DTE, close at 50% max profit OR 7 DTE (whichever first) - LL-268 research
- **Position limit**: 2 iron condors at a time (5% max = $5,000 risk per position)
- **Monthly target**: 3-4 iron condors x $150-250 avg x 86% win rate = $400-860/month (conservative)
- **Stop-loss**: Close if one side reaches 200% of credit - MANDATORY
- **Adjustment**: If tested, roll untested side closer for additional credit
- **Assignment risk**: Close positions at 7 DTE to avoid gamma risk (changed from 21 DTE per LL-268)
- **Risk management**: NEVER more than 5% on single trade. NO NAKED OPTIONS.
- **Paper phase**: 90 days to validate 80%+ win rate before scaling
- **Why iron condors beat credit spreads**: Collect premium from BOTH sides, better win rate, profit in range-bound markets
- **PDT NOTE**: $100K > $25K = NO PDT RESTRICTIONS (can day trade freely)

## Financial Independence Framework (Jan 22, 2026)

### The Four Pillars

1. **Capital Preservation** (Phil Town Rule #1)
   - NEVER lose more than 5% on a single trade
   - Stop-loss at 200% of credit - NO EXCEPTIONS
   - Exit at 7 DTE to avoid gamma risk
   - No naked options, no undefined risk trades

2. **Compounding** (The Wealth Engine)
   - Reinvest 100% of profits during growth phase
   - Returns depend on actual win rate and trade frequency — query RAG for real data
   - DO NOT WITHDRAW until North Star reached

3. **Tax Optimization** (Keep What You Earn) - UPDATED Jan 23, 2026
   - **CRITICAL**: SPY options are EQUITY options - taxed as 100% short-term capital gains
   - **XSP/SPX alternative**: Mini-SPX (XSP) options qualify for Section 1256 (60/40 treatment)
   - Section 1256 benefits: 60% long-term / 40% short-term tax rates, NO wash sale rules
   - **Recommendation**: Evaluate XSP iron condors for ~30% tax savings (see LL-296)
   - Track cost basis for SPY positions (wash sale rules APPLY to SPY)
   - Tax-loss harvest losing SPY trades (offset gains)
   - Estimated tax rate: ~32% for SPY (short-term), ~22% for XSP (60/40 blended)
   - Set aside 30% of profits quarterly for estimated taxes (due Apr 15, Jun 16, Sep 15, Jan 15)
   - File Form 6781 for any Section 1256 contracts (XSP/SPX)

4. **Reinvestment Strategy** (Scale Intelligently)
   - Phase 1 ($100K-$150K): 2 iron condors max, prove the system
   - Phase 2 ($150K-$300K): Scale to 3-4 iron condors if 80%+ win rate
   - Phase 3 ($300K-$600K): 5-6 iron condors, diversify expirations
   - Phase 4 ($600K+): Financial independence reached - withdraw $6K/month

### Path to North Star

**No fabricated projections.** Actual returns tracked in `data/system_state.json`. Query RAG for real performance data before making any scaling decisions. The system proves itself with data, not spreadsheets.

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

| Priority | Ticker | Rationale                                                               |
| -------- | ------ | ----------------------------------------------------------------------- |
| 1        | SPY    | ONLY ticker. Best liquidity, tightest spreads, no early assignment risk |

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
21. **NEVER HARDCODE CREDENTIALS** - No default values in os.environ.get() for secrets (GitGuardian incident Feb 3, 2026)

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

| File                     | Purpose                  | Written By                           |
| ------------------------ | ------------------------ | ------------------------------------ |
| `data/system_state.json` | **CANONICAL** trade data | sync-system-state.yml, trade_sync.py |
| `data/trades_*.json`     | **DEPRECATED**           | Legacy, do not use                   |

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

## RAG Chat (Feb 1, 2026)

Live at: https://igorganapolsky.github.io/trading/rag-query/

- Cloudflare Worker: `cloudflare-workers/rag-chat/worker.js`
- Worker URL: `https://trading-rag-chat.iganapolsky.workers.dev`
- Features: Conversation memory, 10+ embedded lessons, Claude Haiku backend
- API key configured in Cloudflare Workers dashboard

## Date Verification (LL-324 Prevention)

Hook: `.claude/hooks/verify_date_claims.sh`

- Runs on every UserPromptSubmit
- Reminds to verify dates before writing content
- February 2026 key dates embedded (Super Bowl Feb 8, etc.)
- Prevents hallucinations like "Super Bowl weekend" on wrong date

## $100K Paper Account (Jan 30, 2026)

Account ID: PA3C5AG0CECQ - Primary trading account.
Use `ALPACA_PAPER_TRADING_API_KEY` (points to $100K account).
All code must use `get_alpaca_credentials()` from `src/utils/alpaca_client.py`.
**NO PDT RESTRICTIONS** - Can freely close positions same-day.
**DEPRECATED**: $5K and $30K accounts are no longer used.
