# AI Trading System — Trade Velocity Acceleration

## What This Is

An automated iron condor trading system on SPY that needs to accelerate from 1 completed trade in 3 weeks to 30+ completed trades to validate profitability and prove the path to $6,000/month passive income (North Star). The system has infrastructure (GRPO ML brain, Alpaca integration, risk management) but lacks trade volume and completion velocity.

## Core Value

Complete iron condor trades fast enough to prove (or disprove) the system's profitability within 90 days, without violating Phil Town Rule #1 (don't lose money).

## Requirements

### Validated

- Alpaca paper trading integration ($100K account PA3C5AG0CECQ)
- Iron condor order placement (4-leg defined risk)
- GRPO ML parameter optimization (delta/DTE/exit)
- Risk management gates (5% max position, ticker whitelist, stop-loss)
- CI/CD pipeline with automated state sync
- 3 concurrent iron condors currently open

### Active

- [ ] Automated profit-taking at 50% of max credit
- [ ] Automated exit at 7 DTE
- [ ] Scale to 5 concurrent ICs (currently 3)
- [ ] Trade completion tracking with win/loss decomposition
- [ ] Daily P/L attribution (trading vs cash vs interest)
- [ ] 30-trade validation gate before live scaling
- [ ] XSP/SPX migration for 60/40 tax treatment

### Out of Scope

- Live account scaling — until 30+ paper trades validate the system
- Individual stock options — SPY only (lesson learned from SOFI)
- Naked/undefined risk positions — iron condors only

## Context

- Account started at $100K, currently at $100,864 (+0.86%)
- Only 1 completed trade (closed IC on Feb 6-9 for ~$41 profit)
- 3 open ICs (Mar 27, Mar 31, Apr 2 expiry) with -$36 unrealized
- System opens trades but doesn't aggressively manage exits
- North Star requires $350K capital at 2.5%/month = $6K/month
- Current monthly rate (~$400) is nowhere near target
- GRPO optimal: Delta 0.245, DTE 24, Exit 29%

## Constraints

- **Capital**: $100K paper, $200 live — can't scale until validated
- **Risk**: 5% max per position ($5,000), 5 ICs max concurrent
- **Regulatory**: PDT not an issue ($100K > $25K threshold)
- **Tax**: SPY = 100% short-term; need XSP/SPX pivot for 60/40
- **Timeline**: 90-day validation window (started ~Feb 3, 2026)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| SPY only | Best liquidity, tightest spreads, no early assignment | — Pending |
| $10-wide wings | $100K supports wider wings for more premium | — Pending |
| 50% profit target | Balance between win rate and capital efficiency | — Pending |
| 7 DTE exit | Avoid gamma risk (changed from 21 DTE per LL-268) | — Pending |
| GRPO optimization | ML-driven parameter selection vs static rules | — Pending |

---
*Last updated: 2026-02-25 after initialization*
