---
id: LL-317
date: 2026-01-26
severity: critical
status: superseded
category: inventory-reconciliation
---
# Orphan inventory recovery was centralized

Hardcoded symbols, duplicated credential lookup, and generic close-position calls are superseded. Use the central broker factory, reconstruct from filled MLEG orders, use the mandatory gateway, and let `scripts/residual_ic_manager.py` own residual exits. Inventory disagreement blocks successor entries.
