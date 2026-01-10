---
layout: post
title: "Lesson Learned #058: 68% LangSmith Trace Error Rate"
date: 2025-12-23
---

# Lesson Learned #058: 68% LangSmith Trace Error Rate

**ID**: LL-058
**Date**: 2025-12-23
**Severity**: HIGH
**Category**: Observability, Silent Failures
**Impact**: 68% of all traces lost, debugging blind spot

## What Happened

LangSmith dashboard showed 68% error rate across 304 runs. The observability system meant to debug issues was itself broken and silently failing.

## Root Causes (7 Bugs)

1. **Silent exception swallowing** (gates.py:78) - `logger.debug` hid all errors
2. **Double span completion** - Both wrapper and context manager completed spans
3. **AttributeError** (gates.py:1052) - `ctx.macd_signal` doesn't exist, should be `ctx.momentum_signal`
4. **Wrong extra field schema** - Nested dict instead of flat
5. **Empty name validation** - Spans with empty names failed API validation
6. **Inconsistent project names** - 3 different defaults across files
7. **Deprecated datetime** - `datetime.utcnow()` instead of `datetime.now(timezone.utc)`

## Impact

- 68% of debugging information never recorded
- False confidence in observability
- Couldn't diagnose trading failures
- Wasted LangSmith API budget

## Fix Applied

1. Changed `logger.debug` to `logger.warning`
2. Removed manual `span.complete()` calls
3. Fixed attribute name
4. Flattened extra field schema
5. Added fallback name for spans
6. Unified project name to `igor-trading-system`
7. Updated to timezone-aware datetime
8. Added CI verification step (`verify_langsmith.py`)

## Prevention Rules

1. **Test observability code** - Verify traces actually arrive
2. **Never swallow exceptions** - Use `logger.warning` minimum
3. **Add CI verification** - Run `verify_langsmith.py` before trading
4. **Monitor error rates** - 68% should have alerted
5. **Schema validation** - Test trace format before production

## Key Insight

> "The observability system is the last place you expect bugs, but it's also the last place you'd notice them."

## Tags

`langsmith` `observability` `silent-failures` `tracing` `ci-verification`

## Related Lessons

- ll_017: Missing LangSmith env vars
- ll_050: LangSmith tracing integration
- ll_056: Silent pipeline failures
