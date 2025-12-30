---
layout: post
title: "Lesson Learned #045: Verification Systems to Prevent Repeated Mistakes"
date: 2025-12-15
---

# Lesson Learned #045: Verification Systems to Prevent Repeated Mistakes

**ID**: LL-045
**Impact**: Identified through automated analysis

**Date**: December 15, 2025
**Severity**: CRITICAL
**Category**: Process, Verification, RAG, ML
**Requested By**: CEO

---

## Executive Summary

After discovering that we had 64 commits not merged to main, options at wrong allocation, and RAG not being used, the CEO asked: **"What verification can we put in place to avoid such mistakes?"**

This document defines the verification systems that must be in place.

## The Mistakes We Made

| Mistake | Impact | Root Cause |
|---------|--------|------------|
| 64 commits not on main | Tomorrow's trading would use old config | No merge verification |
| Options at 5% instead of 37% | Lost potential profits | Config not updated |
| RAG not queried | Missed lessons from 3 days ago | No enforcement |
| Docs stale | User confusion | No freshness checks |
| Crypto still active | Losing money | No performance monitoring |

## Verification Systems Required

### 1. Session Start Gate (MANDATORY)

**Script**: `scripts/session_start_gate.py`

**Runs**: At the start of every AI session

**Checks**:
- [ ] RAG queried for relevant lessons
- [ ] Documentation freshness verified
- [ ] System state loaded and displayed
- [ ] Recent performance shown
- [ ] Active strategies listed

**Enforcement**: AI must run this before any work.

### 2. Pre-Merge RAG Check (MANDATORY)

**Script**: `scripts/mandatory_rag_check.py`

**Runs**: Before any PR merge

**Checks**:
- [ ] Query RAG for similar past issues
- [ ] Display top 5 relevant lessons
- [ ] Require acknowledgment if critical lessons found

**Enforcement**: Pre-commit hook + CI gate.

### 3. Documentation Freshness Gate (MANDATORY)

**Script**: `scripts/check_doc_freshness.py`

**Runs**: Pre-commit hook

**Checks**:
- [ ] README.md < 7 days old
- [ ] dashboard.md < 3 days old
- [ ] claude-progress.txt < 3 days old
- [ ] system_state.json < 1 day old

**Enforcement**: Commit blocked if stale.

### 4. Strategy Performance Monitor (AUTOMATED)

**Script**: `scripts/daily_pnl_attribution.py`

**Runs**: Daily after market close

**Checks**:
- [ ] P/L attribution by strategy
- [ ] Win rate by strategy
- [ ] Alert if any strategy < 30% win rate
- [ ] Alert if strategy loss > $50

**Enforcement**: GitHub Action + Slack/Email alert.

### 5. Config-to-Lessons Validator (NEW)

**Script**: `scripts/validate_config_against_lessons.py`

**Runs**: Pre-commit hook

**Checks**:
- [ ] Lessons say options = primary → Config has options > 30%
- [ ] Lessons say crypto removed → Config has crypto = 0%
- [ ] Lessons say X strategy bad → Config has X disabled

**Enforcement**: Commit blocked if mismatch.

### 6. Branch-to-Main Sync Check (NEW)

**Script**: `scripts/check_branch_sync.py`

**Runs**: End of every session

**Checks**:
- [ ] All changes committed
- [ ] PR created if changes exist
- [ ] PR merged or merge scheduled
- [ ] Main branch has latest changes

**Enforcement**: Session cannot end without merge.

## Implementation Priority

| System | Priority | Status | Owner |
|--------|----------|--------|-------|
| Session Start Gate | P0 | ✅ Created | CTO |
| Doc Freshness Check | P0 | ✅ Created | CTO |
| Pre-Merge RAG Check | P0 | ✅ Exists | CTO |
| Strategy Performance Monitor | P1 | ⏳ Partial | CTO |
| Config-to-Lessons Validator | P1 | ⏳ TODO | CTO |
| Branch-to-Main Sync | P1 | ⏳ TODO | CTO |

## RAG Integration Requirements

### What Must Be in RAG

1. **All lessons learned** (ll_*.md files)
2. **Performance data** (strategy P/L, win rates)
3. **Configuration history** (allocation changes)
4. **Decision rationale** (why we made changes)

### What Must Be Queried From RAG

1. **Before any strategy change**: "What lessons exist about [strategy]?"
2. **Before any config change**: "What happened last time we changed [config]?"
3. **Before any PR**: "What bugs have we had with [file/feature]?"
4. **At session start**: "What are recent lessons about [current focus]?"

### RAG Query Frequency

| Event | RAG Query Required |
|-------|-------------------|
| Session start | ✅ Yes |
| Before code change | ✅ Yes (if strategic) |
| Before config change | ✅ Yes |
| Before PR merge | ✅ Yes |
| After failure | ✅ Yes (and write lesson) |

## ML Integration Requirements

### What ML Should Learn From

1. **Trade outcomes** → Improve strategy selection
2. **Lesson patterns** → Predict similar failures
3. **Performance trends** → Alert on degradation
4. **Config changes** → Track what works

### ML-Powered Verification

1. **Anomaly Detection**: Alert if strategy behavior differs from historical
2. **Failure Prediction**: Warn if changes match past failure patterns
3. **Performance Forecasting**: Predict next-day P/L based on positions

## Enforcement Mechanisms

### Pre-Commit Hooks

```bash
# .git/hooks/pre-commit
#!/bin/bash
set -e

# 1. Check doc freshness
python3 scripts/check_doc_freshness.py || exit 1

# 2. Run RAG check for changed files
python3 scripts/verify_against_lessons.py || exit 1

# 3. Validate config matches lessons
python3 scripts/validate_config_enums.py || exit 1

echo "✅ All pre-commit checks passed"
```

### CI Gates

```yaml
# .github/workflows/verification-gate.yml
- name: RAG Verification
  run: python3 scripts/mandatory_rag_check.py "$(git diff --name-only HEAD~1)"

- name: Doc Freshness
  run: python3 scripts/check_doc_freshness.py --strict

- name: Config Validation
  run: python3 scripts/validate_config_enums.py
```

### Session End Checklist

Before ending any AI session:
- [ ] All changes committed
- [ ] PR created and merged
- [ ] Main branch updated
- [ ] claude-progress.txt updated
- [ ] Lessons learned documented (if any)

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| RAG query rate | 100% of sessions | Audit log |
| Doc freshness | 100% <3 days | CI check |
| PR merge rate | 100% same day | Git history |
| Lesson compliance | 0 repeated mistakes | Incident count |

## The Philosophy

> "Trust but verify. Automate verification. Make mistakes impossible, not just unlikely."

Every mistake we make should result in:
1. A lesson learned document
2. An automated check to prevent recurrence
3. RAG indexing for future queries
4. ML training data for prediction

**The goal is zero repeated mistakes.**


## Prevention Rules

1. Apply lessons learned from this incident
2. Add automated checks to prevent recurrence
3. Update RAG knowledge base

## Tags

`verification`, `rag`, `ml`, `automation`, `prevention`, `process`, `critical`

## Related Lessons

- LL_035: Failed to Use RAG Despite Building It
- LL_044: Documentation Hygiene Mandate
- LL_043: Crypto Removed - Simplify and Focus

