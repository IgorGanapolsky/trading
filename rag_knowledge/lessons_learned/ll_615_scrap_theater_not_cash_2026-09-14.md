---
id: LL-615
date: 2026-09-14
severity: 5
tags: [cash, scrap, theater, put-credit, scope]
---

# LL-615 — Trading infra theater is not a money system

## Mistake

Agents kept shipping Ralph/GSD 24/7 engines, desk-grade ML/RAG, Dagster clones, Astra harnesses, and Pi integrations while live equity was $0 and put-credit paired n≪30. CEO asked why we are not making money; the honest answer is negative IC edge + paper jail + theater.

## Fix

Close theater PRs without merge. Freeze allowed surfaces in `docs/TRADING_ACTIVE_SCOPE.md`. Fail closed via `scripts/audit_active_scope.py` in `make check` skill-check.

## Prevention

`audit_active_scope.py` requires `paper_only` + `live_blocked` + killed IC families and bans theater filenames.

## Cash routing

Paper fills are not revenue. Route make-money to RealEstate prepaid / agency AHLS / Resume. ThumbGate paid paused while ECI counsel_clearance is false.
