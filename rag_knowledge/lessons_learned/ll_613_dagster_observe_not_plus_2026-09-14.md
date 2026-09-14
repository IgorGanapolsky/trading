# LL-613: Dagster observe/freshness FORMAT (not Dagster+)

**Date**: 2026-09-14
**Severity**: 3
**Category**: harness / paper factory honesty
**Source**: [Dagster docs](https://docs.dagster.io/) (assets, freshness, asset health)

## What transferred

An **asset** is an object in persistent storage. Dagster distinguishes
**materializations** (you computed it) from **observations** (an external
system already has it). Health is the most elevated of latest update,
freshness, and asset checks. ERROR checks block downstream work.

Mapped onto **existing** paper ledgers (not a new orchestrator):

1. `policy/kill_switch` — live_blocked / paper_only / not IC
2. `broker/system_state` — last_updated freshness (24h warn / 72h degrade)
3. `ledger/put_credit_journal` — broker_fill vs submitted_unconfirmed
4. `new_entry_allowed` is false when any ERROR check fails

CLI: `scripts/observe_paper_assets.py --json`

## What did NOT transfer

- Dagster / Dagster+ / Dagit / OpenLineage packages
- In-memory Software-Defined Asset engine (sibling PR #4639 / AGENT-611)
- Makefile `dagster-roi` target (that PR owns it)
- Credit-consuming fake materializations of regime/candidates
- Affiliation with Dagster Labs

Complement, do not dual-edit, #4639.
