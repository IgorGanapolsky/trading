---
layout: post
title: "Lesson Learned: LangSmith Tracing Integration (Dec 16, 2025)"
---

# Lesson Learned: LangSmith Tracing Integration

**ID**: ll_050
**Date**: 2025-12-16
**Severity**: HIGH
**Category**: Observability
**Impact**: Enables full visibility into every trade decision for debugging and compliance

## What Happened

The trading system was making decisions via the RAG/ML trade gate, but these decisions were not being traced to LangSmith. When the CEO checked LangSmith, there were no traces from the trading runs, making it impossible to debug or audit decisions.

## Root Cause

1. The LangSmith tracer module existed (`src/observability/langsmith_tracer.py`) but was NOT wired into the trade gate
2. The `LANGSMITH_API_KEY` was not configured in GitHub Actions workflows
3. Initial integration attempt used context manager incorrectly (manual `__enter__`/`__exit__` calls)

## Solution

1. **Integrated tracing into mandatory trade gate** (`src/safety/mandatory_trade_gate.py`)
   - Every `validate_trade()` call now creates a trace
   - Traces include: symbol, amount, side, strategy, RAG warnings, ML anomalies, decision

2. **Integrated tracing into trade execution** (`src/execution/alpaca_executor.py`)
   - Every executed order is traced
   - Traces include: order details, price, commission, broker

3. **Added workflow configuration** (`.github/workflows/daily-trading.yml`)
   - `LANGSMITH_API_KEY` and `LANGCHAIN_API_KEY` environment variables
   - `LANGCHAIN_PROJECT` set to "ai-trading-system"
   - `LANGCHAIN_TRACING_V2` enabled

4. **Added verification script** (`scripts/verify_trade_gate_tracing.py`)
   - Run manually to confirm tracing is working

## Prevention Rules

1. **ALWAYS trace critical decisions** - Any decision that could lose money MUST be traced
2. **Use context managers correctly** - Use `with tracer.trace() as span:` not manual __enter__/__exit__
3. **Check observability after deployment** - Verify traces appear in LangSmith after each deploy
4. **Add API keys to workflows** - Any new observability tool needs its secrets in GitHub Actions

## Code Pattern

```python
# CORRECT usage of LangSmith tracer
from src.observability.langsmith_tracer import TraceType, get_tracer

def my_decision_function():
    if LANGSMITH_AVAILABLE:
        tracer = get_tracer()
        with tracer.trace(
            name="my_decision",
            trace_type=TraceType.DECISION,
        ) as span:
            span.inputs = {"key": "value"}
            result = do_work()
            span.add_output("result", result)
            span.add_metadata({"context": "info"})
    return result
```

## Files Modified

- `src/safety/mandatory_trade_gate.py` - Added `_trace_gate_decision()` method
- `src/execution/alpaca_executor.py` - Added `_trace_trade_execution()` method
- `.github/workflows/daily-trading.yml` - Added LangSmith environment variables
- `scripts/verify_trade_gate_tracing.py` - New verification script

## Action Required

**You MUST add `LANGSMITH_API_KEY` to GitHub Secrets:**
1. Go to: Settings → Secrets → Actions
2. Click "New repository secret"
3. Name: `LANGSMITH_API_KEY`
4. Value: Your key from https://smith.langchain.com
