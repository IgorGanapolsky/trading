---
layout: post
title: "Lesson Learned: Dashboard Workflow Failed Due to GPU Requirements (Dec 12, 2025)"
---

# Lesson Learned: Dashboard Workflow Failed Due to GPU Requirements (Dec 12, 2025)

**ID**: LL-021
**Impact**: Identified through automated analysis

## Incident ID: LL-021
## Severity: HIGH
## Category: workflow_bug, ci_cd, dependencies

## What Happened

The dashboard-auto-update workflow was consistently failing at the "Install dependencies" step. The workflow tried to install the full `requirements.txt` which contains 183 packages including GPU/CUDA dependencies that cannot be installed on GitHub Actions runners.

**Timeline:**
- Dec 12: Dashboard workflow failing at "Install dependencies"
- Dashboard not updating with current P/L data
- Root cause identified: `pip install -r requirements.txt` trying to install nvidia-*, torch, triton packages

**Error Pattern:**
```
pip install -r requirements.txt
ERROR: Could not find a version that satisfies the requirement nvidia-cublas-cu12
```

## Root Cause

1. `requirements.txt` was designed for local development with GPU support
2. Dashboard workflow doesn't need ML/GPU packages - only needs Alpaca API and basic Python
3. GitHub Actions runners don't have GPU support
4. No validation existed to prevent this misconfiguration

## Prevention Fix

### 1. Created Minimal Requirements File
```
# requirements-dashboard.txt
alpaca-py>=0.43.0      # Alpaca API for account data
python-dotenv>=1.0.0   # Environment variables
numpy>=1.26.0          # Basic calculations
```

### 2. Updated Workflow
```yaml
# BEFORE (broken)
pip install -r requirements.txt

# AFTER (fixed)
pip install -r requirements-dashboard.txt
```

### 3. Added Automated Tests
- `tests/test_workflow_dependencies.py` - Catches this issue automatically
- Tests that lightweight workflows don't use full requirements.txt
- Tests that minimal requirements files don't have GPU packages

### 4. RAG Pre-Deployment Check
- `scripts/rag_pre_deployment_check.py` - Queries lessons learned before deployment
- Warns if changes match patterns of past failures

## Verification Checklist

After any workflow change:
- [ ] Run `pytest tests/test_workflow_dependencies.py`
- [ ] Check that lightweight workflows use minimal requirements
- [ ] Run `python scripts/rag_pre_deployment_check.py --check-workflows`

## Related Issues

- LL-020: Trade files not committed (same workflow, different issue)
- LL-019: Trading system dead for 2 days

## Tags
`workflow` `dependencies` `requirements` `gpu` `ci-cd` `github-actions` `dashboard`

## Knowledge Graph Links
- Pattern: workflow_dependency_mismatch
- Prevention: use_minimal_requirements_for_ci
- Test: test_workflow_dependencies.py
