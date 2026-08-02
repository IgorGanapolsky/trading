# Trading Rules

## Canonical Policy Constants

- LEGACY_IC_STOP_LOSS_MULTIPLIER: 2.0 (exit-only inventory)
- NORTH_STAR_MONTHLY_AFTER_TAX: 6000
- MAX_POSITIONS: 8

## Active Strategy: SPY Put Credit

- Paper-only SPY bull-put credit spreads through `scripts/spy_put_credit.py`.
- The strategy kill switch is authoritative; killed families cannot submit new entries.
- Use one-lot, $5-wide structures with a roughly 15-delta short strike and 30–45 DTE.
- Maximum 3 structures per day and 2 concurrent structures.
- Define a 200%-of-credit stop, a 25% profit target, and a 7-DTE time exit.
- Residual iron-condor inventory is exit-only through `scripts/residual_ic_manager.py`.
- Live capital stays blocked until at least 30 broker-reconciled, paired closures show
  positive expectancy and profit factor above 1.

## Pre-Trade Checklist

1. [ ] Ticker is SPY.
2. [ ] Paper mode is explicit and live submission is blocked.
3. [ ] The order is a one-lot, defined-risk, two-leg bull-put spread.
4. [ ] Both strikes are present in the current option chain.
5. [ ] Short strike is approximately 15 delta and expiration is 30–45 DTE.
6. [ ] Stop-loss, profit target, and time exit are defined before submission.
7. [ ] Open inventory is reconciled with `scripts/audit_open_inventory.py`.
8. [ ] The strategy kill switch permits the put-credit family.
9. [ ] Entry and exit journals reconcile to broker orders.

## Ticker Selection

| Priority | Ticker | Rationale |
| --- | --- | --- |
| 1 | SPY | Required ticker; deepest liquidity and tight spreads for the validation cohort. |

Do not open new positions in individual stocks.

## Evidence and Projection Rules

- Track every paper trade: entry, exit, P/L, and outcome.
- Required metrics are win rate, average win, average loss, profit factor, and expectancy.
- Evaluate only paired, broker-reconciled closed trades from the active strategy family.
- Do not project returns until at least 30 qualifying closures exist.
- Do not extrapolate daily or weekly returns to monthly or yearly timeframes.
- Do not attribute P/L to a strategy without decomposing it by order source.
- Validate P/L with `validate_pl_report()` from `src/utils/pl_validator.py` when available.
- When asked how much was made, show the decomposed evidence rather than one headline number.

## Archived Iron-Condor Policy

Iron condors are killed for new risk. Historical structure rules are retained only to
interpret exit-only inventory: $5-wide wings, 30–45 DTE, 200%-of-credit stop, 25%
profit target, and 7-DTE time exit.
