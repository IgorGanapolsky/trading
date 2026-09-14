---
id: LL-616
date: 2026-09-14
severity: 5
tags: [buffett, put-credit, rebuild, capital-preservation, north-star]
---

# LL-616 — Buffett Rule #1 rebuild (Sept 2026 research)

## Context

CEO: destroy the system, start over with a winning strategy, do not lose money,
North Star = $6,000/mo after-tax. Parallel.ai deep research was out of credit;
used free web rails + local ledger.

## Research that drove the rebuild

- OptionKrafter Aug 2026: under realistic fills, only ~60 DTE SPY put-credit
  stayed positive across 7/14/30/45/60 arms.
- OptionKrafter Sept 2026: 0DTE iron condors can win ~75% and still lose.
- Professional premium-seller rulebooks: TP ~50% credit, stop ~2x, defined risk.
- Buffett/Phil Town: only risk capital you can lose; size small; defined risk.

## Implementation

Default profile `spy-put-credit-buffett`: 60 DTE target, TP 50%, stop 200%,
1 concurrent / 1 daily, SPY>=200DMA hard, max loss <=1% equity. Live blocked.

## Prevention

Hypothesis JSON + controlled-experiment.md + tests/test_buffett_rebuild.py.
