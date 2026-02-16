---
layout: "post"
title: "Daily Dashboard Snapshot - 2026-02-16"
description: "Daily snapshot for 2026-02-16: paper equity $101,441.56, paper daily P/L $0.00, cadence gate FAIL."
date: "2026-02-16"
last_modified_at: "2026-02-16"
tags:
  - "dashboard"
  - "north-star"
  - "ai-discoverability"
  - "ops"
image: "/assets/og-image.png"
canonical_url: "https://igorganapolsky.github.io/trading/reports/2026-02-16-dashboard-snapshot/"
faq: true
questions:
  - question: "What is the current state of the trading system today?"
    answer: "Daily snapshot for 2026-02-16: paper equity $101,441.56, paper daily P/L $0.00, cadence gate FAIL."
  - question: "Are cadence and risk gates passing this week?"
    answer: "Cadence gate is FAIL. Risk mode is validation with recommended max position size 0.0%."
  - question: "What is the North Star probability right now?"
    answer: "North Star probability is 36.40% (low), target date 2029-11-14."
---
# Daily Dashboard Snapshot | 2026-02-16

This report is auto-generated from system state for search and AI discoverability.

## Answer Block

**Q: Did we make money today?**<br>
A: Paper daily P/L is $0.00. Live account total P/L is $147.48.

**Q: Are we on track toward the North Star?**<br>
A: North Star probability is 36.40% (low), target date 2029-11-14.

**Q: Is execution cadence healthy?**<br>
A: Weekly cadence KPI is **FAIL** with risk mode **validation**.

## KPI Snapshot

| Metric | Value |
|---|---|
| Live Equity | $167.48 |
| Live Total P/L | $147.48 (737.40%) |
| Paper Equity | $101,441.56 |
| Paper Total P/L | $1,441.56 (1.44%) |
| Paper Daily Change | $0.00 |
| Paper Win Rate | 100.00% (sample: 1) |
| Open Positions (Paper) | 4 |
| Weekly Cadence KPI | FAIL |
| Weekly Risk Mode | validation |
| Recommended Max Position Size | 0.01% |
| North Star Probability | 36.40% (low) |

## Evidence

- [System state source](https://github.com/IgorGanapolsky/trading/blob/main/data/system_state.json)
- [Dashboard source markdown](https://github.com/IgorGanapolsky/trading/blob/main/wiki/Progress-Dashboard.md)
- [Cadence gate checker](https://github.com/IgorGanapolsky/trading/blob/main/scripts/check_weekly_cadence_gate.py)
- [North Star operating plan updater](https://github.com/IgorGanapolsky/trading/blob/main/scripts/update_north_star_operating_plan.py)
- [Live site dashboard](https://igorganapolsky.github.io/trading/)

## Data Freshness

- Snapshot date: `2026-02-16`
- Live account sync timestamp: `2026-02-16T17:13:14.638362`
