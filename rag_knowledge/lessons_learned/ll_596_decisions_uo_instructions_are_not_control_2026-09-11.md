# LL-596: Decisions UO FORMAT — instructions are not control

**Date**: 2026-09-11
**Severity**: 3
**Category**: governance / process record
**Source**: Decisions ebook _Universal Orchestration / Who Governs the Machines?_
([PDF](https://cdn.sanity.io/files/a9zf4mro/production/3a1a4f21b38cef8a635d7f6487d7bfa95fb05de2.pdf))

## What transferred

Gartner UO three capabilities, mapped onto **existing** spy_put_credit rails:

1. Runtime coordination — factory may paper-submit; occupancy 2/2 waits
2. State outside the agent — ledgers are the process record, not chat context
3. Control before action — `instructions_are_not_control`; live still human-gated

CLI: `python scripts/put_credit_govern.py`

The ebook’s Replit/Cursor lesson (“instructions are not control”) is already why
`mandatory_trade_gate` exists. This record makes **where / stuck / next** visible
so a green cron cannot hide a stall.

## What did NOT transfer

- Decisions product / BOAT / a ThumbGate universal-orchestrator SKU
- Multi-vendor agent fabric
- Token-cost dashboards as a new product
- Live capital

Monetize path remains n≥30 paper put-credit with expectancy>0.
