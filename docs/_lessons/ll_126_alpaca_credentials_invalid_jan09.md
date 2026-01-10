---
layout: post
title: "LL-126: Alpaca API Credentials Invalid - 401 Unauthorized"
date: 2026-01-09
---

# LL-126: Alpaca API Credentials Invalid - 401 Unauthorized

**ID**: LL-126
**Date**: 2026-01-09
**Severity**: CRITICAL
**Category**: Operations/API

## Executive Summary

Both the GitHub Secrets AND the credentials provided by CEO are returning 401 Unauthorized from Alpaca API.

## Evidence

From GitHub Actions workflow logs:
```
401 Client Error: Unauthorized for url: https://paper-api.alpaca.markets/v2/account
alpaca.common.exceptions.APIError: {"message": "unauthorized."}
```

## Credentials Tested

1. **GitHub Secrets** (ALPACA_PAPER_TRADING_5K_API_KEY): FAILED
2. **CEO-provided credentials**: FAILED

## Root Cause

The Alpaca API credentials are invalid. Possible reasons:
1. Keys were regenerated in Alpaca dashboard after being saved
2. Paper trading account was reset/closed
3. Keys are for wrong account type (live vs paper)
4. Keys expired or were revoked

## Resolution Required

1. Log into https://app.alpaca.markets
2. Navigate to Paper Trading account
3. Verify paper trading is enabled
4. Regenerate API keys if needed
5. Update GitHub secrets with new keys

## Impact

- Paper trading has been broken since Jan 6 (4 days)
- No trades can execute until credentials are fixed
- System health checks fail at Alpaca connectivity step

## Prevention

- Add credential expiration monitoring
- Test credentials weekly even without trades
- Alert when credentials fail validation

## Tags

#alpaca #api #unauthorized #credentials #critical #ll-126
