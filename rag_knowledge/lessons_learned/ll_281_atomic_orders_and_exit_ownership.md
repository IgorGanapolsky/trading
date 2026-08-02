---
id: LL-281
date: 2026-01-22
severity: critical
status: resolved
category: order-execution
---
# Atomic orders and one broker-reconciled exit owner

Independent leg orders, guessed prices, and several close scripts produced partial structures and ambiguous ownership. Entries/exits use atomic MLEG intents through `TradeGateway`; strikes come from a validated live chain; residual killed-strategy inventory is owned only by `scripts/residual_ic_manager.py`.
