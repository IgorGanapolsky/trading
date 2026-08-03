---
id: LL-272
date: 2026-01-21
severity: critical
status: superseded
category: trading-safety
---

# Rogue entry paths and PDT blocked recovery

Multiple entry surfaces opened non-policy or incomplete positions, and a small account could not immediately close the exposure because of broker PDT protection. Current rule: one paper entry owner, SPY-only validation, atomic defined-risk MLEG orders, and broker-reconciled inventory before new risk. A recovery plan must use broker truth and must not assume a same-day close is available.
