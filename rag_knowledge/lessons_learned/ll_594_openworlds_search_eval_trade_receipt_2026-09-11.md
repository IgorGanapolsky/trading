# LL-594: OpenWorlds search→evaluate→trade FORMAT (not a clone)

**Date**: 2026-09-11
**Severity**: 3
**Category**: harness / validation cadence
**Source**: [OpenWorlds](https://www.openworlds.ai/) (Dillon Kay / OpenWorlds AGI, Inc.)

## What transferred

Public pitch: personal trading agent; agents that **search, evaluate, and trade**
with autonomy; action logs and results as the product surface; non-custodial
(they do not hold keys).

Mapped onto **existing** `spy_put_credit` paper factory + JIT harness:

1. **SEARCH** — kill switch, inventory, `--status` (cohort n / occupancy).
2. **EVALUATE** — `--dry-run`; cite blockers; plan ≠ fill.
3. **TRADE** — weekday `--execute-paper` only; live remains blocked.
4. **RECEIPT** — submitted 0/1 + the gate that fired (green cron is not a fill).

JIT task class: `discovery_loop` (`src/ops/jit_harness.py`).

## What did NOT transfer

- OpenWorlds product / “create an agent” SKU
- Wallet / delegated signing / non-custodial custody theater
- RL / fleet self-improvement from user action logs
- Simulators as a replacement for the n=30 paired ledger
- Outreach to Dillon or claiming affiliation

Monetize path remains n≥30 paper put-credit with expectancy>0 — not a new agent marketplace.
