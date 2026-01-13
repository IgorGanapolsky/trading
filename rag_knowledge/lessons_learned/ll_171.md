---
id: ll_171
title: Phil Town Rule #1 Violated - Lost $17.94 on Jan 13
severity: CRITICAL
date: 2026-01-13
category: trading
tags: [rule-one, loss, risk-management]
---

## Problem
Phil Town Rule #1: "Don't lose money" - VIOLATED on Jan 13, 2026.

## Evidence
- Portfolio: $4,969.94 (-0.36%)
- Daily Loss: -$17.94
- SOFI stock: 22.74 shares, -$0.94 loss
- SOFI PUT: 2 contracts, -$7.00 loss

## Root Cause
1. Sold 2 SHORT PUTS instead of 1 (doubled exposure)
2. Market moved against position
3. No stop-loss or protective measures in place

## Lesson
1. NEVER double down on losing positions
2. Use position sizing: max 1 CSP per symbol at a time
3. Set mental stop-loss at 50% premium loss
4. Monitor positions intraday

## CEO Directive
"We are not allowed to lose money" - This must be prevented.

## Prevention
- Add position limit check before opening new CSP
- Alert when daily P/L exceeds -$10
- Review positions before market close
