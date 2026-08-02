---
id: LL-282
date: 2026-01-22
severity: critical
status: resolved
category: incident-response
---
# Recovery must fail closed and preserve broker truth

Freeze new entries, reconcile broker inventory and fills, identify one exit owner, submit only structure-aware recovery intents, and verify acceptance/fills before changing the ledger. Tests, workflow completion, and journal edits are not position-closure evidence.
