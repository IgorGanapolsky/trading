# Trading Rules

## Strategy: Iron Condors on SPY

- Sell 15-20 delta put spread (bull put) + 15-20 delta call spread (bear call)
- $10-wide wings, 30-45 DTE ($100K account supports wider wings for more premium)
- Collect $150-250 per IC per side with $10-wide strikes
- 5 concurrent ICs across different expiry cycles (weekly/monthly)
- 15-delta = 86% win rate (LL-220), risk/reward ~1.5:1

## Pre-Trade Checklist (MANDATORY)

1. [ ] Ticker = SPY (ONLY — best liquidity, tightest spreads)
2. [ ] Position size ≤ 5% of account ($5,000 risk)
3. [ ] Iron condor (4-leg, defined risk on BOTH sides)
4. [ ] Short strikes at 15-20 delta
5. [ ] 30-45 DTE expiration
6. [ ] Stop-loss at 200% of credit defined
7. [ ] Exit plan: 50% profit OR 7 DTE (LL-268)

## Ticker Selection

| Priority | Ticker | Rationale                                                               |
| -------- | ------ | ----------------------------------------------------------------------- |
| 1        | SPY    | ONLY ticker. Best liquidity, tightest spreads, no early assignment risk |

**NO individual stocks.** $100K success was SPY. $5K failure was SOFI.

## Win Rate Tracking

- Track every paper trade: entry, exit, P/L, win/loss
- Required metrics: win rate %, avg win, avg loss, profit factor
- < 80% after 30 trades: check delta selection, may need wider wings
- 80-85%: on track, maintain discipline
- 85%+: profitable, consider scaling after 90 days

## Projection Rules (MANDATORY)

- NO return projections until 30+ completed iron condor trades exist
- NO extrapolating daily/weekly returns to monthly/yearly timeframes
- NO attributing P/L to iron condors without decomposing by order source
- All P/L claims MUST use `validate_pl_report()` from `src/utils/pl_validator.py`
- If asked "how much did we make" — show decomposed report, not a single number

## Phil Town Alignment

Iron condors align with Rule #1:

- Defined risk on BOTH sides (put AND call spread)
- 15-delta = ~85% probability of profit
- 1.5:1 reward/risk ratio (vs credit spreads' 0.5:1)
- Profit if SPY stays within range
