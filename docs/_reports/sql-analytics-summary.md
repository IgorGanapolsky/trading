---
title: "Automated SQL Analytics Summary"
description: "Latest period-over-period trading analytics summary generated from canonical trading JSON sources."
image: "/assets/snapshots/progress_latest.png"
date: "2026-03-13T21:19:27.211433+00:00"
severity: "INFO"
category: "analytics"
---

# Automated SQL Analytics Summary

**Date**: 2026-03-13T21:19:27.211433+00:00
**Severity**: INFO
**Category**: analytics

## Summary
Automated period-over-period analytics summary generated from canonical trading JSON sources. Use this record to answer day-over-day, week-over-week, expectancy, cadence, and North Star progress questions in the published RAG query experience.

## Evidence
- Published SQL analytics JSON: https://github.com/IgorGanapolsky/trading/blob/main/docs/data/sql_analytics_summary.json
- SQLite analytics builder: https://github.com/IgorGanapolsky/trading/blob/main/src/analytics/sqlite_analytics.py

## Answer Block
Q: How did today compare to the previous snapshot?
A: Equity is $98,527.33, resolved daily P/L is $581.72, and the change versus the previous snapshot is $-1,995.43.

Q: What changed in closed-trade performance?
A: The latest closed-trade day is 2026-02-06; realized P/L is $41.00, delta versus the previous closed-trade day is n/a, and cumulative realized P/L is $41.00.

Q: What changed week over week on the North Star?
A: The latest North Star week is 2026-03-09; probability is 49.70% (low), expectancy per trade is $-5,822.50, and expectancy delta versus the prior week is $-1,786.17.

## Highlights
- Equity declined by $1,995.43 versus the previous snapshot, with resolved daily P/L $581.72.
- Closed-trade ledger now contains 1 closed trade(s); latest realized P/L was $41.00 on 2026-02-06.
- North Star weekly gate is blocked; probability label is LOW and monthly target remains $6,000.00.

## Full Summary

# SQL Analytics Summary

- Generated at: `2026-03-13T21:19:27.211433+00:00`
- SQLite DB: `/Users/ganapolsky_i/workspace/git/igor/trading/.worktrees/rag-analytics-answers/artifacts/devloop/trading_analytics.sqlite`

## Source Coverage
- Account snapshots loaded: `15`
- Closed trades loaded: `1`
- Weekly North Star rows loaded: `5`

## Account Daily PoP
- Snapshot date: `2026-03-13`
- Equity: `$98,527.33`
- Resolved daily P/L: `$581.72`
- Prior equity: `$100,522.76`
- Equity change vs prior snapshot: `$-1,995.43`
- Equity change % vs prior snapshot: `-1.99%`
- Rolling 5D P/L: `$585.64`
- Trade activity: orders `n/a`, structures `n/a`, fills `n/a`

## Closed Trade PoP
- Trade date: `2026-02-06`
- Closed trades on date: `1`
- Realized P/L: `$41.00`
- Realized P/L delta: `n/a`
- Expectancy per trade: `$41.00`
- Cumulative realized P/L: `$41.00`

## North Star Weekly PoP
- Week start: `2026-03-09`
- Monthly target: `$6,000.00`
- Probability: `49.70%` (`low`)
- Monthly progress: `2.05%`
- Expectancy per trade: `$-5,822.50`
- Expectancy delta vs prior week: `$-1,786.17`
- Weekly win rate: `0.00%`
- Weekly cadence passed: `False`

## Highlights
- Equity declined by $1,995.43 versus the previous snapshot, with resolved daily P/L $581.72.
- Closed-trade ledger now contains 1 closed trade(s); latest realized P/L was $41.00 on 2026-02-06.
- North Star weekly gate is blocked; probability label is LOW and monthly target remains $6,000.00.


## Tags
`rag`, `analytics`, `period-over-period`, `expectancy`, `cadence`, `north-star`
