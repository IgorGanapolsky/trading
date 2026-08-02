# Trading Rules

## Canonical Policy Constants

- IRON_CONDOR_STOP_LOSS_MULTIPLIER: 2.0 (CEO-approved 2026-07-02, validation cohort; was 1.0)
- NORTH_STAR_MONTHLY_AFTER_TAX: 6000
- MAX_POSITIONS: 8

## Active Strategy (post IC kill, 2026-07-22)

**Primary entry: `spy_put_credit` (paper only).** See `data/runtime/strategy_kill_switch.json`
and `.claude/rules/kill-criteria.md` / `controlled-experiment.md`.

- SPY 1-lot bull put credit, $5 wide, 15Δ short, 30–45 DTE
- Max 3 structures/day, max 2 concurrent
- Stop at 200% of credit; profit take 25%; exit by 7 DTE
- Live capital blocked until cohort n≥30 with expectancy>0 and PF>1

### Iron Condor — KILLED for new entries

- Do **not** open new iron condors via `ic_simple.py`, `iron_condor_trader.py`, or
  disabled IC workflows.
- Residual IC legs: exit/manage only via guardian / `ic_simple.py --mode exit`.
- Historical IC rules below are **archive context only**, not active North Star path.

## Pre-Trade Checklist (MANDATORY) — put credit

1. [ ] Ticker = SPY (ONLY)
2. [ ] Paper account only (`spy_put_credit`)
3. [ ] 1-lot defined-risk put credit (2-leg)
4. [ ] Short strike ~15 delta
5. [ ] 30–45 DTE
6. [ ] Stop-loss at 200% of credit defined
7. [ ] Exit plan: 25% profit OR 7 DTE
8. [ ] Open inventory clean (`scripts/audit_open_inventory.py`)
9. [ ] Broker state fresh; kill switch allows put-credit family

## Ticker Selection

| Priority | Ticker | Rationale                                                               |
| -------- | ------ | ----------------------------------------------------------------------- |
| 1        | SPY    | ONLY ticker. Best liquidity, tightest spreads, no early assignment risk |

**NO individual stocks.** $100K success was SPY. $5K failure was SOFI.

## Win Rate Tracking

- Track every paper trade: entry, exit, P/L, win/loss
- Required metrics: win rate %, avg win, avg loss, profit factor, expectancy
- Gate on expectancy > 0 and PF > 1 over 30 clean put-credit trades — not headline win rate alone

## Projection Rules (MANDATORY)

- NO return projections until 30+ completed put-credit validation trades exist
- NO extrapolating daily/weekly returns to monthly/yearly timeframes
- All P/L claims MUST use paired ledger (`data/trades.json`) + `validate_pl_report()` when available
- If asked "how much did we make" — show decomposed report, not a single number

## Archive — historical IC structure (killed for new risk)

- Sell 15-20 delta put spread + 15-20 delta call spread
- $5-wide wings, 30-45 DTE, 2 concurrent ICs max (8 legs)
- Stop 200% credit; exit 25% profit OR 7 DTE
