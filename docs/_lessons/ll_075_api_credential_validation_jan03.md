---
layout: post
title: "API Key Validation Before Trading"
date: 2026-01-03
category: infrastructure
severity: critical
---
layout: post

## Summary

Alpaca API keys can become invalid without warning. Always validate keys before assuming trading will work.

## Key Insight

API keys returning "Access denied" on BOTH paper and live endpoints means the keys are invalid/expired - NOT an endpoint mismatch issue.

## Evidence

```bash
# Both endpoints failed with same error:
curl https://api.alpaca.markets/v2/account → Access denied
curl https://paper-api.alpaca.markets/v2/account → Access denied
```

## Root Cause

- API keys may expire or be revoked
- Keys may not have trading permissions
- Account may need re-verification

## Prevention

1. **Pre-trade validation**: Always test API connection before market open
2. **Health checks**: Add API key validation to daily workflow
3. **Alerting**: Fail fast with clear error when keys invalid

## Action Items

- [ ] Add API key validation to SessionStart hook
- [ ] Create GitHub Action to test API connectivity daily
- [ ] Store key validation timestamp in system_state.json
