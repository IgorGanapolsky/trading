# Kill Criteria — Strategy Lifecycle

## IC Simple — KILLED (2026-07-22)

**Status: KILLED** as a North Star candidate.

| Metric (lifetime paired ledger) | Value |
|----------------------------------|-------|
| Closed trades | ~174 |
| Win rate | ~17% |
| Profit factor | 0.70 |
| Expectancy | ~−$32 / trade |
| Realized P/L | ~−$5.6k |

**Do not reopen IC Simple entries.** Exit/manage existing legs only via guardian.

Successor: **`spy_put_credit`** (see `data/runtime/strategy_kill_switch.json`).

---

## Active: SPY Put Credit Validation

### Hypothesis

2-leg SPY bull put credit (1-lot, $5 wide, 15Δ short, 30–45 DTE, 25% TP / 200% stop / 7 DTE exit)
can produce **expectancy > 0** and **PF > 1** over **30** clean paper trades — without the
4-leg inventory failure modes of iron condors.

### Kill Conditions (ANY triggers removal of put-credit as North Star candidate)

1. **Expectancy ≤ 0** after 30 closed validation trades (put-credit cohort only)
2. **Profit factor ≤ 1.0** after 30 closed validation trades
3. **Win rate below break-even** given realized avg win/loss
4. **3 consecutive max-loss stops** in the cohort
5. **Account drawdown > 10%** from validation start equity at cohort begin

### If killed

- `spy_put_credit` removed as North Star candidate
- New written hypothesis required (do not silently resume IC)
- No "just keep trading"

### Hard constraints while validating

- Paper only; live blocked
- SPY only; 1-lot; max 1 structure/day; max 2 concurrent
- No 10-wide wings; no naked options; no multi-name underlyings
- Unclean open inventory blocks new entries
