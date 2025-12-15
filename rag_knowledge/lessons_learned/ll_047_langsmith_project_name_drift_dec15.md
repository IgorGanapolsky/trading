# Lesson Learned: LangSmith Project Name Drift (Dec 15, 2025)

**ID**: ll_047
**Date**: December 15, 2025
**Severity**: MEDIUM
**Category**: Observability, Configuration Drift, Consistency
**Impact**: Dashboard appeared broken - traces sent to wrong project for weeks

## Executive Summary

LangSmith dashboard showed only 1 trace while the system was actively trading. Root cause: project name inconsistency across 8 files. Workflows sent traces to `trading-system` while the dashboard showed `igor-trading-system`.

## The Mistake

### What Happened

| Metric | Value |
|--------|-------|
| Files with wrong project name | 8 |
| Days without proper observability | Unknown (potentially weeks) |
| Dashboard project name | `igor-trading-system` |
| Actual project name in code | `trading-system`, `trading-rl-training` |

### Root Cause Analysis

1. **No Single Source of Truth**: Project name hardcoded in 8 different locations
2. **Silent Failure**: Wrong project name doesn't error - just creates traces elsewhere
3. **No Verification Test**: No automated check to ensure consistency
4. **Copy-Paste Drift**: Each workflow copied settings independently, allowing divergence

### The Configuration Fragmentation

```yaml
# What we had (inconsistent):
daily-trading.yml:       LANGCHAIN_PROJECT: 'trading-system'
weekend-crypto.yml:      LANGCHAIN_PROJECT: 'trading-system'
rl-training.yml:         LANGCHAIN_PROJECT: 'trading-system'
model-training.yml:      LANGCHAIN_PROJECT: 'trading-system'
combined-trading.yml:    LANGCHAIN_PROJECT: 'trading-system'
rl_orchestrator.py:      LANGCHAIN_PROJECT: 'trading-rl-training'  # Different!
configure_langsmith.sh:  LANGSMITH_PROJECT: 'igor-trading-system'  # The actual one!

# What we need (single source):
# All files use: LANGCHAIN_PROJECT: 'igor-trading-system'
```

## The Fix

### Immediate Actions (Dec 15)

1. Unified all 8 files to use `igor-trading-system`:
   - `.github/workflows/daily-trading.yml`
   - `.github/workflows/weekend-crypto-trading.yml`
   - `.github/workflows/rl-training-continuous.yml`
   - `.github/workflows/model-training.yml`
   - `.github/workflows/combined-trading.yml`
   - `.env.example`
   - `src/utils/langsmith_wrapper.py`
   - `scripts/rl_training_orchestrator.py`

2. Created verification test (see below)

### Prevention Rules

#### Rule 1: Configuration Consistency Test

```python
def test_ll_047_langsmith_project_consistency():
    """Ensure all LangSmith project names are consistent."""
    import re
    from pathlib import Path

    EXPECTED_PROJECT = "igor-trading-system"
    patterns = [
        (r"LANGCHAIN_PROJECT[=:]\s*['\"]?([^'\"\\s]+)", "workflows/scripts"),
        (r"LANGSMITH_PROJECT[=:]\s*['\"]?([^'\"\\s]+)", "shell scripts"),
    ]

    files_to_check = [
        ".github/workflows/daily-trading.yml",
        ".github/workflows/weekend-crypto-trading.yml",
        ".github/workflows/rl-training-continuous.yml",
        ".github/workflows/model-training.yml",
        ".github/workflows/combined-trading.yml",
        ".env.example",
        "src/utils/langsmith_wrapper.py",
        "scripts/rl_training_orchestrator.py",
        "scripts/configure_langsmith.sh",
    ]

    for filepath in files_to_check:
        path = Path(filepath)
        if not path.exists():
            continue
        content = path.read_text()
        for pattern, desc in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                assert match == EXPECTED_PROJECT, \
                    f"REGRESSION ll_047: {filepath} has project '{match}' but expected '{EXPECTED_PROJECT}'"
```

#### Rule 2: Pre-Commit Hook for Config Drift

Add to `.pre-commit-config.yaml`:
```yaml
- repo: local
  hooks:
    - id: langsmith-project-consistency
      name: Check LangSmith project name consistency
      entry: python3 -c "exec(open('tests/test_observability.py').read()); test_ll_047_langsmith_project_consistency()"
      language: system
      pass_filenames: false
```

#### Rule 3: Centralize Configuration

Instead of hardcoding in each file, use a single source:
```python
# config/observability.py
LANGSMITH_PROJECT = "igor-trading-system"
```

## Verification Tests

### Test 1: Project Name Consistency
```python
def test_ll_047_langsmith_project_consistency():
    """All LangSmith configs must use 'igor-trading-system'."""
    # Implementation above
```

### Test 2: Trace Destination Verification
```python
def test_langsmith_trace_destination():
    """Verify traces actually go to the right project."""
    import os
    os.environ["LANGCHAIN_PROJECT"] = "igor-trading-system"

    from src.utils.langsmith_wrapper import get_project_name
    assert get_project_name() == "igor-trading-system"
```

## Metrics to Track

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| LangSmith traces per workflow run | ≥ 1 | 0 |
| Project name consistency | 100% | Any mismatch |
| Dashboard last trace age | < 24h on trading days | > 48h |

## Key Quotes

> "Silent configuration drift is the worst kind - it doesn't break, it just stops working."

> "If you have the same value in 8 files, you have 8 opportunities for drift."

> "Verify the obvious - 'dashboard is broken' often means 'looking at wrong dashboard'."

## Integration with ML Pipeline

### 1. RAG Pattern Detection
Add embeddings for:
- "langsmith not showing traces"
- "dashboard empty"
- "project name mismatch"
- "observability not working"

### 2. Automated Audits
Weekly configuration consistency check:
```python
def weekly_config_audit():
    """Run as GitHub Action on schedule."""
    test_ll_047_langsmith_project_consistency()
    # Alert on failure
```

## Related Lessons

- `ll_017_missing_langsmith_env_vars_dec12.md` - Missing env vars (different issue, same system)
- `ll_030_langsmith_deep_agent_observability.md` - LangSmith integration patterns
- `ll_045_verification_systems_prevent_mistakes_dec15.md` - Verification prevents issues

## Tags

#observability #langsmith #configuration-drift #consistency #verification #autonomous-detection

## Change Log

- 2025-12-15: Initial incident discovered and fixed
- 2025-12-15: Added to RAG knowledge base with verification test
