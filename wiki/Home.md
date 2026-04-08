# SPY Options Validation Platform Wiki

Generated from canonical ledgers at `2026-04-08T20:03:21.036829+00:00`.

This wiki is generated from the same source used by the public dashboard and repo copy. It should never carry frozen win-rate, equity, or trade-count claims that drift from the ledgers.

## Current Snapshot

- Public status: `halted`
- Paper equity: `$93,838.30`
- Closed trades total: `66`
- Total realized P/L: `$-3,402.00`
- Weekly gate mode: `defensive`

## Key Links

- [Public dashboard](https://igorganapolsky.github.io/trading)
- [Operator dashboard](https://igorganapolsky.github.io/trading/rag-query.html)
- [Progress Dashboard](Progress-Dashboard)
- [Development Engine and Evidence](Development-Engine-and-Evidence)

## Operating Truth

This project is currently a paper-first validation platform, not a proven passive-income engine. Public surfaces should show current gate state and broker-backed evidence rather than frozen claims.

## Current Blocker

`CRITICAL: Weekly gate conflicts with lifetime paired-trade ledger. Lifetime ledger shows 66 closed trades, expectancy $-51.55/trade, profit factor 0.25, total realized P/L $-3402.00. Block new positions until lifetime edge is positive.`
