# Lesson Learned: LangSmith Dashboard Empty Despite Configuration

**ID**: ll_051
**Date**: 2025-12-17
**Severity**: HIGH
**Category**: Observability, Configuration, CI/CD
**Impact**: CEO unable to audit trade decisions - trading blind for days

## Executive Summary

The LangSmith dashboard showed only 1 trace from Dec 12 despite configuration appearing correct in GitHub workflows. Root cause: multiple validation gaps allowed trading to proceed without functional observability.

## What Happened

1. **Dec 12**: LangSmith verification test created single trace
2. **Dec 15**: Last actual trade executed (BTC buy)
3. **Dec 16**: LangSmith properly integrated into trade gate (#718, #720)
4. **Dec 16-17**: All trading decisions were SKIPs (market below MA)
5. **Dec 17**: CEO checks dashboard - only sees 1 old trace

## Root Causes

### 1. LANGCHAIN_API_KEY Not Validated
`scripts/validate_secrets.py` did NOT include `LANGCHAIN_API_KEY` in any validation list:
- If GitHub Secret didn't exist, workflow ran with empty key
- LangSmith silently failed - no error, just no traces

### 2. Tracing Health Check Didn't Block
The pre-trade tracing health check in the workflow only warned but proceeded anyway:
```python
# OLD CODE (BAD):
if not result.healthy:
    print('⚠️ TRACING HEALTH CHECK FAILED')
    print('Trading will proceed but may not be fully traced!')  # DANGEROUS
```

### 3. Traces Only on Actual Trades
LangSmith traces were wired into `AlpacaExecutor.place_order()` and `mandatory_trade_gate`. But when strategies SKIP (no trade), the executor is never called - no trace generated.

### 4. Timing Gap
LangSmith integration merged Dec 16 17:28, but last actual trade was Dec 15 01:03. No trades since integration = no traces to see.

## The Fix

### 1. Added LANGCHAIN_API_KEY to Validation (CRITICAL)
```python
# scripts/validate_secrets.py
observability_secrets = [
    "LANGCHAIN_API_KEY",  # LangSmith tracing - REQUIRED for trade decision audit
]

# Validation fails if missing
return len(missing_critical) == 0 and len(missing_observability) == 0, errors
```

### 2. Tracing Health Check Now Blocks Trading
```yaml
# .github/workflows/daily-trading.yml
if not result.healthy:
    print('❌ TRACING HEALTH CHECK FAILED')
    print('CEO MANDATE: Trading WITHOUT observability is FORBIDDEN!')
    sys.exit(1)  # BLOCK TRADING
```

### 3. Added LANGCHAIN_API_KEY to Workflow Validation Step
```yaml
- name: Validate secrets
  env:
    LANGCHAIN_API_KEY: ${{ secrets.LANGCHAIN_API_KEY }}  # NOW VALIDATED
```

## Prevention Rules

1. **ALL secrets that affect observability must be validated**
2. **Health checks must BLOCK, not warn** - proceeding blind is unacceptable
3. **Check workflow runs after integration** - verify traces appear
4. **Add traces to SKIP decisions too** - not just actual trades

## Action Required

**Verify GitHub Secret exists:**
1. Go to repo Settings → Secrets and variables → Actions
2. Confirm `LANGCHAIN_API_KEY` exists
3. If missing, get from https://smith.langchain.com/settings

## Files Modified

- `scripts/validate_secrets.py` - Added LANGCHAIN_API_KEY validation
- `.github/workflows/daily-trading.yml` - Block on tracing failure

## Verification

Next workflow run will either:
- ✅ Pass and generate traces visible in LangSmith
- ❌ Fail early with clear error about missing LANGCHAIN_API_KEY

## Related Lessons

- `ll_017_missing_langsmith_env_vars_dec12.md` - First LangSmith gap
- `ll_050_langsmith_tracing_integration_dec16.md` - Trade gate integration

## Tags

#langsmith #observability #validation #secrets #ci-cd #debugging

## Change Log

- 2025-12-17: Incident diagnosed and fixed
