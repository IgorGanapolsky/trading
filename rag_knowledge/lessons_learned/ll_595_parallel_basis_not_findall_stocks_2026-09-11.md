# LL-595: Parallel Basis FORMAT, not FindAll stocks

**Date**: 2026-09-11
**Severity**: 3
**Category**: evidence / discovery loop
**Source**: [Parallel.ai](https://parallel.ai/?shem=dsdf,sharefoc,agadiscoversdl,,sh/x/discover/m1/4)

## What transferred

Parallel public pitch: Search / Extract / Monitor / Discover / Enrich, with
**Basis** (citation + calibrated confidence) on every claim. Discovery returns
**entities**, not links.

Mapped onto **local** `spy_put_credit` ledgers:

- SEARCH cites `strategy_kill_switch.json` (family, paper_only, live_blocked)
- EVALUATE cites journal open count + paired `trades.json` n toward 30
- TRADE is receipt-only (`submitted: 0`); no Parallel API call
- Confidence is high/medium/low from file presence, not a fake model score

CLI: `python scripts/put_credit_basis.py --json`

## What did NOT transfer

- Parallel Task / Search / FindAll / Monitor APIs in the hot path (cost + SPY-only)
- "Find all tickers" (controlled experiment is SPY put-credit)
- Untracked primary-checkout theater (`parallel_ai_features.py`,
  `integrated_parallel_trading.py`, simulated prices)
- Claiming AUM/Sharpe from n=3

Monetize path remains n≥30 paired put-credit with expectancy>0.
