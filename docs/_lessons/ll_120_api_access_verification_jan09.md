---
layout: post
title: "LL-120: API Access Verification Required Before Trading"
date: 2026-01-09
---

# LL-120: API Access Verification Required Before Trading

**ID**: LL-120
**Date**: 2026-01-09
**Severity**: CRITICAL
**Category**: Operations/API
**Impact**: Cannot execute trades without API access

## Executive Summary

During session Jan 9, 2026, CTO discovered that Alpaca API calls return "Access denied" from sandbox environment, despite paper account showing $5,000 balance in Alpaca dashboard.

## The Problem

1. Paper API: `curl -H "APCA-API-KEY-ID: ..." https://paper-api.alpaca.markets/v2/account` returns "Access denied"
2. Brokerage API: Same "Access denied" response
3. Sandbox cannot verify positions or execute trades
4. system_state.json sync_mode shows "skipped_no_keys"

## Evidence

From session:
```
Paper API: "Access denied"
Brokerage API: "Access denied"
sync_mode: "skipped_no_keys"
```

Screenshot evidence shows paper account has $5,000 (confirmed by CEO), but API calls fail.

## Root Cause Analysis

Possible causes:
1. API keys may be invalid or rotated
2. Sandbox network may be blocked from Alpaca
3. Rate limiting or IP restrictions
4. Keys need regeneration in Alpaca dashboard

## Impact

- Cannot verify positions for risk management
- Cannot execute trades from sandbox
- Cannot sync to Vertex AI RAG (no keys)
- System not operationally secure

## Resolution Path

1. **Immediate**: Use CI workflows (daily-trading.yml) which have credentials via GitHub Secrets
2. **Verify**: Check GitHub Actions logs for successful API calls
3. **If CI works**: Sandbox issue is network/IP based
4. **If CI fails**: API keys need regeneration

## Lesson Learned

**Always verify API access at session start before claiming operational readiness.**

Pre-session checklist should include:
```bash
# Test paper API
curl -s -H "APCA-API-KEY-ID: $KEY" https://paper-api.alpaca.markets/v2/account

# Test brokerage API
curl -s -H "APCA-API-KEY-ID: $KEY" https://api.alpaca.markets/v2/account
```

If either fails, immediately flag to CEO and use CI as fallback.

## Files

- system_state.json (sync_mode: skipped_no_keys)
- .github/workflows/daily-trading.yml (has secrets)

## Tags

#api #alpaca #access-denied #operational-security #ll-120
