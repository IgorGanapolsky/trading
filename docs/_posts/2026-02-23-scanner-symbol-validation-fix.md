---
title: "Fix: Validate Option Symbols Before Trading"
date: 2026-02-23
last_modified_at: "2026-02-23"
description: "How a missing symbol validation caused weeks of failed trades and the two-layer defense fix"
tags: [iron-condor, alpaca, options, bug-fix, trading-system]
categories: [lessons-learned]
canonical_url: https://igorganapolsky.github.io/trading/lessons-learned/scanner-symbol-validation-fix/
---

## The Problem

Our iron condor scanner picked option expirations mathematically — any Friday in the 30-45 DTE window. But Alpaca doesn't list weekly option contracts months in advance. When the scanner chose April 3, 2026 (a Friday, 39 DTE), the symbols `SPY260403P00640000` didn't exist yet.

Result: `APIError: invalid legs` on every scan for weeks. Zero trades executed.

## Root Cause

`find_expiration_date()` calculated dates without querying the broker. Weekly SPY options are only listed ~2-3 weeks before expiration. Monthly options (third Fridays) are listed months ahead.

## The Fix

Two-layer defense:

**Layer 1 — Smart Expiry Discovery**: Query Alpaca's `OptionChainRequest` API for real expirations. Only return dates where contracts actually exist. Fall back to third Fridays (monthly — always listed).

**Layer 2 — Symbol Validation**: Before submitting any order, verify all 4 OCC symbols exist via `OptionSnapshotRequest`. If any symbol is missing, abort with a clear error.

## Result

First autonomous trade in weeks submitted at 17:50 UTC on Feb 23, 2026. Both Scanner and Autonomous workflows green.

## Lesson

Never assume financial instrument availability from date math. Always validate against the broker's actual listings before constructing orders.

---

*Related: [Complete Guide to AI Iron Condor Trading](/trading/2026/01/21/iron-condors-ai-trading-complete-guide/) | [Our North Star Strategy](/trading/2026/02/17/north-star-operating-strategy/)*
