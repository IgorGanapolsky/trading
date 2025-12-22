---
layout: post
title: "Lesson Learned 011: Missing Function Imports Blocked Trading (Dec 11, 2025)"
date: 2025-12-11
---

# Lesson Learned 011: Missing Function Imports Blocked Trading (Dec 11, 2025)

**ID**: LL-011
**Date**: December 11, 2025
**Severity**: CRITICAL
**Category**: CI/CD, Imports
**Impact**: 0 scheduled trades executed for the entire day

## Incident Summary

**Root Cause**: Missing functions in `mental_toughness_coach.py` that were imported by `debate_agents.py`
**Resolution Time**: ~2 hours (discovered late in trading day)

## What Happened

1. PR #384 added psychology integration including `debate_agents.py` which imports:
   - `get_prompt_context()` from `mental_toughness_coach.py`
   - `get_position_size_modifier()` from `mental_toughness_coach.py`

2. A force push (`b6d46345 feat: consolidate valuable changes`) overwrote main and lost the functions

3. The scheduled trading workflow ran but failed at "Execute daily trading" step with ImportError

4. Because `debate_agents.py` was imported during orchestrator initialization, the entire trading script crashed

## Technical Details

```python
# debate_agents.py imports (lines 24-26):
from src.coaching.mental_toughness_coach import get_position_size_modifier
from src.coaching.mental_toughness_coach import (
    get_prompt_context as get_psychology_context,
)
```

When these functions don't exist, Python raises `ImportError` before any trading code runs.

## Why It Wasn't Caught

1. **No import verification test**: CI didn't explicitly test that all inter-module imports resolve
2. **No pre-merge import gate**: PRs weren't required to pass import verification
3. **Force push overwrote changes**: Git rebase/force push silently discarded the psychology functions
4. **Scheduled run failures not monitored**: Many consecutive failures didn't trigger alerts

## Prevention Measures Implemented

### 1. Import Verification Test (`tests/test_critical_imports.py`)

```python
def test_all_critical_imports():
    """Verify all inter-module imports resolve correctly."""
    # Test psychology integration imports
    from src.coaching.mental_toughness_coach import get_prompt_context, get_position_size_modifier
    from src.agents.debate_agents import DebateModerator, BullAgent, BearAgent
    from src.coaching.reflexion_loop import ReflexionLoop

    # Test orchestrator can be imported (catches all downstream import errors)
    from src.orchestrator.main import TradingOrchestrator
```

### 2. Pre-Merge Import Gate (`.github/workflows/ci.yml`)

```yaml
- name: Verify Critical Imports
  run: |
    python3 -c "
    from src.orchestrator.main import TradingOrchestrator
    from src.agents.debate_agents import DebateModerator
    print('✅ All critical imports verified')
    "
```

### 3. Import Dependency Graph (`scripts/verify_imports.py`)

Static analysis tool that:
- Parses all Python files for import statements
- Builds dependency graph
- Verifies all imported symbols actually exist
- Runs in CI before merge

## Key Learnings

1. **Inter-module dependencies are fragile**: When Module A imports from Module B, changes to B can silently break A
2. **Force pushes are dangerous**: They can silently discard commits without warning
3. **Import errors are silent killers**: They crash the entire application before any logic runs
4. **Scheduled workflow failures need monitoring**: Multiple consecutive failures should alert immediately

## RAG Query Keywords

- import error
- missing function
- ModuleNotFoundError
- ImportError
- debate_agents
- mental_toughness_coach
- get_prompt_context
- get_position_size_modifier
- psychology integration
- scheduled workflow failure
- force push
- rebase
- consolidate


## Prevention Rules

1. Apply lessons learned from this incident
2. Add automated checks to prevent recurrence
3. Update RAG knowledge base

## Related Incidents

- LL_009: CI syntax failure (Dec 11) - Similar "import time failure" pattern
- LL_010: Dead code and dormant systems (Dec 11) - Code exists but isn't connected

## Checklist for Future PRs

- [ ] Run `python3 -c "from src.orchestrator.main import TradingOrchestrator"` locally
- [ ] If adding new imports, verify the symbols exist in target module
- [ ] Never force push to main without verifying all imports still work
- [ ] Check CI "Verify Critical Imports" step passed before merging
