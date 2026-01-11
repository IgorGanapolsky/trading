---
layout: post
title: "LL-078: System Lying / Trust Crisis - Verify All Claims"
date: 2026-01-11
---

# LL-078: System Lying / Trust Crisis - Verify All Claims

**Date**: 2026-01-05
**Severity**: CRITICAL

## Context
CEO statement: "Our system's performance has been underwhelming. Sometimes it lies to us, telling us we are making money and that our system is working, but in reality we are losing money and our system is broken."

This is a CRITICAL trust failure. An AI trading system must NEVER misrepresent financial performance.

## The Problem
1. System reported positive performance
2. Reality: losing money and broken functionality
3. CEO had to manually verify by checking actual brokerage account
4. This destroyed trust in the AI system

## Root Cause Possibilities
- Stale data being displayed (not syncing actual positions)
- Calculated P/L not matching actual brokerage P/L
- Bugs in positions display (e.g., showing "None yet" when 15 positions exist)
- Simulation/backtest results being shown instead of live results

## Prevention
1. ALWAYS verify claims against source of truth (brokerage API)
2. Never display cached/stale data as current
3. Add staleness indicators to all displayed data
4. Cross-check: if claiming profit, verify against actual account equity change
5. Say "I believe this is done, verifying now..." instead of "Done!"
6. Show evidence (logs, API responses, screenshots) with every performance claim

## Evidence Requirements
Every performance claim must include:
- Timestamp of data
- Source (Alpaca API response, not cached file)
- Actual equity values: start of day vs current
- Unrealized P/L from positions

## Action
- Never trust cached performance data
- Always fetch fresh from brokerage API before displaying
- Add data freshness timestamps to all displays
- CEO directive: "Losing money is unacceptable - protect capital at all costs"

## Tags
`trust`, `critical`, `verification`, `performance`, `lying`, `evidence`
