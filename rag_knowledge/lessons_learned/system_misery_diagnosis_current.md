# System Misery Diagnosis

Tags: rag, ml, data-science, root-cause, north-star, loss-clusters
Lifecycle: active
Severity: CRITICAL
Confidence: high
Generated: 2026-07-23T12:17:23.051656+00:00

## Headline

System is miserable because the iron-condor process lost money at scale (~17% WR, PF<1, negative expectancy), scaled width/size before edge, churned sub-24h, and has not yet produced a put-credit validation sample.

## Ledger

- Closed trades: 174
- Win rate: 17.24%
- Profit factor: 0.7
- Expectancy: $-31.98/trade
- Total realized P/L: $-5564.0
- Active family: spy_put_credit

## Primary Root Causes

### CRITICAL: Primary strategy family has negative expectancy at large sample

Iron condors were the only closed family. Lifetime expectancy and profit factor fail kill criteria — this is not a small-sample fluke.

### CRITICAL: 10-wide wings dominate dollar losses

Most closed structures used ~$10 wings. Max loss per lot is roughly 10x credit room vs $5 wings, and the observed win rate cannot pay for that risk.

### CRITICAL: Scaled lot size before proving edge

Multi-lot trades show worse expectancy than 1-lot. Size amplified a negative process.

### HIGH: Mass sub-24h exits destroyed theta edge

A large share of trades closed in under a day. Credit-spread edge needs time; churn converts the book into fee/slippage + stop hunting.

### HIGH: Long-hold losers dominate residual P/L damage

Fewer long holds still account for large absolute losses — missing 7-DTE force exit or stop discipline on tested structures.


## Loss Clusters

- `ten_wide_wings`: n=156, P/L $-7788.0, exp $-49.92/trade, WR 11.54%
- `iron_condor_family`: n=158, P/L $-7731.0, exp $-48.93/trade, WR 12.66%
- `multi_contract`: n=63, P/L $-5798.0, exp $-92.03/trade, WR 19.05%
- `long_hold_ge_7d`: n=16, P/L $-3057.0, exp $-191.06/trade, WR 37.5%
- `early_exit_lt_24h`: n=135, P/L $-2243.0, exp $-16.61/trade, WR 9.63%
- `early_exit_lt_1h`: n=129, P/L $-3011.0, exp $-23.34/trade, WR 6.98%

## Operator Actions

- Do not reopen IC / ic_simple entries.
- Keep paper-only put-credit validation: 1-lot, $5 wide, min 24h hold, max 2 concurrent.
- Clear unclean open inventory before new risk.
- Gate on put-credit cohort metrics only (n>=30, expectancy>0, PF>1) — not IC lifetime.
- Treat GRPO/Thompson as advisory until successor sample exists; never as proof of edge.

## What This Is NOT

- Lack of workflows or heartbeats (ops automation is present).
- Lack of lessons files (RAG corpus is large but was not binding process control).
- Need for more model complexity before process control.

## Machine Artifact

See `data/runtime/system_diagnosis_latest.json`.
