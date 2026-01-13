---
layout: post
title: "Deleting 7,000 Lines of Dead Code: A Technical Debt Story"
date: 2026-01-12
categories: [technical, lessons]
tags: [refactoring, clean-code, technical-debt]
description: "How we found and removed 7,000+ lines of dead code from our AI trading system. Tools, process, and lessons."
---

# The Technical Debt Reckoning

Yesterday, we ran a comprehensive audit of our codebase. What we found was embarrassing.

## The Numbers

- **Dead agent stubs**: 5 files that did nothing
- **Unused scripts**: 18 files never called by any workflow
- **Placeholder tests**: 14 tests with just `assert True`
- **Duplicate code**: 6 sentiment modules with 80% overlap

Total dead code: **~7,000 lines**

## How Did This Happen?

Fast iteration during R&D. We tried things, they didn't work, we moved on. But we never cleaned up.

Sound familiar?

## The Audit Process

We used 5 parallel AI agents to scan the entire codebase:

1. **Agent 1**: Scan `src/` for dead code and DRY violations
2. **Agent 2**: Scan `tests/` for coverage gaps
3. **Agent 3**: Scan docs for outdated content
4. **Agent 4**: Scan CI/CD for reliability issues
5. **Agent 5**: Scan scripts for unused files

Each agent returned a detailed report in under 2 minutes.

## What We Deleted

### Dead Agent Stubs
```
- src/agents/fallback_strategy.py  # Always returned False
- src/agents/meta_agent.py         # Always returned None
- src/agents/research_agent.py     # Empty implementation
- src/agents/signal_agent.py       # Returned empty list
- src/agents/risk_agent.py         # Duplicated RiskManager
```

These files existed because "we might need them later." We didn't.

### Placeholder Tests

Found in `test_orchestrator_main.py`:
```python
def test_psychology_gate_concept(self):
    assert True  # Placeholder

def test_momentum_gate_concept(self):
    assert True  # Placeholder
```

These tests were **lying about coverage**. They passed but tested nothing.

We deleted 13 fake tests and added 5 real smoke tests.

## The Security Fix

While auditing CI/CD, we found this:

```yaml
- name: Setup GCP Auth
  run: |
    echo "$GCP_SA_KEY" > /tmp/gcp_sa_key.json
    # Missing: chmod 600
```

GCP credentials were world-readable. Fixed with one line:
```yaml
    chmod 600 /tmp/gcp_sa_key.json
```

## Lessons Learned

1. **Dead code is lying code** - It implies functionality that doesn't exist
2. **Placeholder tests are worse than no tests** - They give false confidence
3. **Regular audits are essential** - Technical debt compounds

## The Result

- **Lines removed**: 7,000+
- **Files deleted**: 26
- **Security fixes**: 3
- **Time spent**: 2 hours

The codebase is leaner, more honest, and more maintainable.

## How to Do Your Own Audit

1. Use parallel agents to scan different areas
2. Look for: unused imports, unreachable code, `pass` statements
3. Check tests for `assert True` or low-value assertions
4. Verify CI/CD actually validates what it claims to

Don't wait 74 days like we did.

---

*Technical debt cleanup documented in LL-145, LL-146, LL-147. [See all lessons](/trading/lessons/)*
