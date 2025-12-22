---
layout: post
title: "Lesson Learned: Missing LangSmith Environment Variables in Workflows (Dec 12, 2025)"
---

# Lesson Learned: Missing LangSmith Environment Variables in Workflows (Dec 12, 2025)

**ID**: ll_017
**Date**: December 12, 2025
**Severity**: MEDIUM
**Category**: Observability, CI/CD, Environment Configuration
**Impact**: No LLM tracing in production, blind to model behavior and costs

## Executive Summary

GitHub Actions workflows had `HELICONE_API_KEY` configured for cost tracking but were missing
`LANGCHAIN_API_KEY` for LangSmith tracing. This meant all OpenRouter LLM calls were
executing without detailed observability, making it impossible to debug model behavior,
track token usage, or identify prompt issues in production.

## The Mistake

### What Happened

| Metric | Value |
|--------|-------|
| PR Number | #565 |
| Affected Workflows | daily-trading.yml, weekend-crypto-trading.yml |
| Days Without Tracing | Unknown (weeks/months) |
| Traces Lost | All production LLM calls |

### Root Cause Analysis

1. **Partial Observability Setup**: Only Helicone (cost tracking) was configured, not LangSmith (detailed traces)
2. **Similar Variable Names**: `LANGCHAIN_ENABLE_MCP` and `LANGCHAIN_MODEL` existed but are NOT tracing vars
3. **No Verification**: No test to verify observability stack is complete
4. **Silent Failure**: Missing env vars don't cause errors - they just disable features

### The Configuration Gap

```yaml
# What we HAD (incomplete):
HELICONE_API_KEY: ${{ secrets.HELICONE_API_KEY }}  # ✅ Cost tracking
LANGCHAIN_ENABLE_MCP: ${{ secrets.LANGCHAIN_ENABLE_MCP || 'true' }}  # ❌ Not tracing
LANGCHAIN_MODEL: ${{ secrets.LANGCHAIN_MODEL || '...' }}  # ❌ Not tracing

# What we NEEDED (complete):
HELICONE_API_KEY: ${{ secrets.HELICONE_API_KEY }}  # Cost tracking
LANGCHAIN_API_KEY: ${{ secrets.LANGCHAIN_API_KEY }}  # ✅ Tracing auth
LANGCHAIN_PROJECT: 'trading-rl-training'  # ✅ Project name
LANGCHAIN_TRACING_V2: 'true'  # ✅ Enable tracing
```

## The Fix

### Immediate Actions (Dec 12)

1. **Added LangSmith Env Vars** to both workflows (PR #565):
   - `LANGCHAIN_API_KEY: ${{ secrets.LANGCHAIN_API_KEY }}`
   - `LANGCHAIN_PROJECT: 'trading-rl-training'`
   - `LANGCHAIN_TRACING_V2: 'true'`

2. **Added GitHub Secret**: `LANGCHAIN_API_KEY` with LangSmith API key

3. **Verified Local .env**: Added same vars for local development

### Prevention Rules

#### Rule 1: Observability Stack Checklist

When adding LLM calls, verify ALL observability is configured:

| Component | Env Var | Purpose |
|-----------|---------|---------|
| LangSmith Auth | `LANGCHAIN_API_KEY` | API authentication |
| LangSmith Tracing | `LANGCHAIN_TRACING_V2=true` | Enable trace capture |
| LangSmith Project | `LANGCHAIN_PROJECT` | Dashboard organization |
| Helicone Gateway | `HELICONE_API_KEY` | Cost tracking |

#### Rule 2: Workflow Env Var Verification Script

Create automated check that runs in CI:

```python
def verify_workflow_observability():
    """Ensure workflows have complete observability config."""
    required_vars = [
        'LANGCHAIN_API_KEY',
        'LANGCHAIN_TRACING_V2',
        'LANGCHAIN_PROJECT',
        'HELICONE_API_KEY'
    ]

    workflows = [
        '.github/workflows/daily-trading.yml',
        '.github/workflows/weekend-crypto-trading.yml'
    ]

    for workflow in workflows:
        content = Path(workflow).read_text()
        for var in required_vars:
            assert var in content, f"Missing {var} in {workflow}"
```

#### Rule 3: Test Observability in CI

```yaml
- name: Verify observability stack
  env:
    LANGCHAIN_API_KEY: ${{ secrets.LANGCHAIN_API_KEY }}
  run: |
    python3 -c "
    from src.utils.langsmith_wrapper import get_observability_status
    status = get_observability_status()
    assert status['langsmith']['enabled'], 'LangSmith not configured!'
    assert status['helicone']['enabled'], 'Helicone not configured!'
    print('✅ Observability stack verified')
    "
```

## Verification Tests

### Test 1: Workflow Contains Required Env Vars
```python
def test_ll_017_workflow_observability_vars():
    """Ensure trading workflows have all observability env vars."""
    import yaml
    from pathlib import Path

    required_vars = ['LANGCHAIN_API_KEY', 'LANGCHAIN_TRACING_V2', 'LANGCHAIN_PROJECT']

    for workflow_file in ['.github/workflows/daily-trading.yml',
                          '.github/workflows/weekend-crypto-trading.yml']:
        content = Path(workflow_file).read_text()
        for var in required_vars:
            assert var in content, f"REGRESSION ll_017: Missing {var} in {workflow_file}"
```

### Test 2: LangSmith Wrapper Enables Tracing
```python
def test_langsmith_wrapper_enables_tracing():
    """Verify langsmith wrapper properly configures tracing."""
    import os
    os.environ['LANGCHAIN_API_KEY'] = 'test_key'

    from src.utils.langsmith_wrapper import is_langsmith_enabled
    assert is_langsmith_enabled(), "LangSmith should be enabled when API key is set"
```

## Metrics to Track

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| LangSmith traces per day | ≥ 10 | 0 |
| Trace success rate | 100% | < 95% |
| Env var coverage | 100% | Any missing |

## Key Quotes

> "Observability that's partially configured is invisibility."

> "Similar variable names (`LANGCHAIN_*`) don't mean similar purposes."

> "If you can't see what your LLMs are doing, you can't improve them."

## Integration with ML Pipeline

### 1. RAG Pattern Detection
Add pattern to detect incomplete observability setups:
- Search for `HELICONE_API_KEY` without `LANGCHAIN_API_KEY`
- Flag workflows missing any observability var

### 2. Automated Audits
Weekly script to verify all secrets are configured:
```python
required_secrets = [
    'LANGCHAIN_API_KEY',
    'HELICONE_API_KEY',
    'OPENROUTER_API_KEY'
]
# Check via GitHub API
```

## Related Lessons

- `ll_009_ci_syntax_failure_dec11.md` - CI gaps allowing bad merges
- `ll_010_dead_code_and_dormant_systems_dec11.md` - Unconfigured systems

## Tags

#observability #langsmith #helicone #env-vars #ci #workflows #configuration #tracing #llm

## Change Log

- 2025-12-12: Initial incident discovered and fixed (PR #565)
- 2025-12-12: Added to RAG knowledge base
