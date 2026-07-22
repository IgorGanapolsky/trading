# LL-360 — IC Simple Killed; SPY Put Credit Successor (2026-07-22)

## Decision

**KILL** `ic_simple` / `iron_condor` as North Star entry strategies.

## Evidence

- Lifetime paired ledger (~174 closes): WR ~17%, PF 0.70, expectancy ~−$32, realized ~−$5.6k
- Dominant loss clusters: 10-wide wings, multi-lot, sub-24h churn, dual-side inventory orphans
- Post-rehab 1-lot IC n=4 wins is **not** sufficient to overturn lifetime failure
- CEO directive: scrap prior system for a better validation design

## Successor

`spy_put_credit` — 2-leg SPY bull put credit, paper-only, 1-lot, $5 wide, 15Δ, 30–45 DTE, 25% TP / 200% stop / 7 DTE exit.

## Enforcement

- `data/runtime/strategy_kill_switch.json`
- `src/core/active_strategy.py`
- Entry blocked in `scripts/ic_simple.py` and `scripts/iron_condor_trader.py`
- New plan path: `scripts/spy_put_credit.py`

## Not claimed

Put credit is **not** proven profitable. It is a **cleaner experiment**. Edge requires n≥30 with expectancy>0 and PF>1.
