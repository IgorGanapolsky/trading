---
id: LL-326
date: 2026-01-23
severity: high
status: resolved
category: option-selection
---
# Select strikes from a validated live chain

Arithmetic rounding once produced nonexistent strikes. Select contracts from the live chain, validate symbol/expiry/type/strike and quote freshness, then submit the structure atomically. A guessed fallback is not a tradable contract.
