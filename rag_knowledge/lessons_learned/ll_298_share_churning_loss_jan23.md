---
id: LL-298
title: $22.61 Loss from SPY Share Churning - Crisis Workflow Failure
date: 2026-01-23
severity: CRITICAL
category: trading
---

## Incident
Lost $22.61 on January 23, 2026 from 49 SPY share trades instead of iron condor execution.

## Root Cause
1. Crisis workflows traded SPY SHARES (not options)
2. Iron condor failed due to:
   - Wrong GitHub secret names (5K vs 30K) → credentials None
   - Invalid expiration date (Feb 22 = Sunday)

## Prevention
1. DISABLE all crisis workflows permanently
2. Verify GitHub secrets match workflow env vars
3. Always validate Friday expiration before placing orders
4. Add circuit breaker: if >5 share trades per day, HALT

## Lesson
Phil Town Rule #1 violated. Never let automated workflows trade shares.
Iron condors ONLY. No exceptions.
