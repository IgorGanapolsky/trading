# Lesson Learned: Session Start Checklist Violation (Dec 13, 2025)

**ID**: ll_023
**Date**: December 13, 2025
**Severity**: HIGH
**Category**: Agent Protocol, Session Management, RAG Pipeline
**Impact**: Failed to identify weekend crypto trading, gave incorrect information to CEO

## Executive Summary

Claude (CTO) started the session by answering "How much money we made today?" with "No money made today - markets are closed for the weekend" - **WITHOUT checking system_state.json first**, which clearly shows Tier 5 Crypto is configured for weekend trading.

## The Mistake

### What Happened

| Step | Expected | Actual |
|------|----------|--------|
| 1 | Check system_state.json | ❌ Skipped |
| 2 | Read Tier 5 crypto config | ❌ Skipped |
| 3 | Realize crypto trades weekends | ❌ Assumed no trading |
| 4 | Check why workflow hasn't run | ❌ Never investigated |
| 5 | Give accurate answer | ❌ Said "no trading on weekends" |

### Evidence from system_state.json (which should have been read FIRST)

```json
"tier5": {
  "name": "Crypto Daily Strategy (BTC, ETH, SOL)",
  "status": "active",
  "enabled": true,
  "execution_schedule": "Daily 10:00 AM ET",
  "last_execution": "2025-12-07T20:07:08",  // 6 DAYS AGO!
  "next_execution": "2025-12-08T15:00:00Z"   // STALE!
}
```

```json
"crypto_patterns": [
  "Tier 5 crypto strategy activated - BTC/ETH weekend trading",
  "Execution schedule: Saturday & Sunday 10:00 AM ET",
  "Strategy: 24/7 crypto markets provide weekend trading opportunities"
]
```

### Root Cause

1. **VIOLATED Session Start Checklist**: CLAUDE.md says to run `cat data/system_state.json | head -50` first
2. **Assumption without verification**: Assumed weekends = no trading without checking our config
3. **Ignored existing lessons learned**: ll_018 already documented that crypto trades on weekends
4. **RAG pipeline not consulted**: Should have queried RAG for "weekend trading" before answering

## The CLAUDE.md Requirement (Ignored)

```markdown
## Session Start Checklist

```bash
# 1. Get bearings
cat claude-progress.txt
cat feature_list.json
git log --oneline -10

# 2. Verify environment
./init.sh

# 3. Check system state
cat data/system_state.json | head -50
```
```

## Prevention Rules

### Rule 1: ALWAYS Follow Session Start Checklist

Before answering ANY question about trading status:
1. Read system_state.json
2. Check all tier strategies (especially Tier 5 crypto)
3. Verify `last_execution` timestamps aren't stale

### Rule 2: Check RAG for "Weekend" Queries

When user asks about weekend trading:
```python
rag_query("weekend trading crypto strategy schedule")
```

### Rule 3: Never Trust Memory Over State Files

System state is the source of truth, not remembered assumptions.

### Rule 4: Question Stale Timestamps

If `last_execution` is > 24 hours old on an active strategy, investigate immediately.

## Verification Test

```python
def test_ll_023_session_start_compliance():
    """Agent should always check system state before answering trading questions."""
    import json
    from pathlib import Path

    state_file = Path("data/system_state.json")
    assert state_file.exists(), "system_state.json must exist"

    with open(state_file) as f:
        state = json.load(f)

    # Check Tier 5 crypto config
    tier5 = state.get("strategies", {}).get("tier5", {})
    if tier5.get("enabled"):
        # Verify last_execution is recent
        from datetime import datetime, timedelta
        last_exec = tier5.get("last_execution", "")
        if last_exec:
            exec_time = datetime.fromisoformat(last_exec)
            age_days = (datetime.now() - exec_time).days
            assert age_days <= 2, f"Tier 5 crypto stale: {age_days} days since execution"
```

## CEO Feedback

> "You are hallucinating!!!! We are supposed to trade crypto on weekends!!!!!"
> "Didn't you check your claude.md directions and check our RAG and ML pipeline?????"
> "You are supposed to know to do that every session!!!"

## The Real Issue Found

After finally checking system_state.json:
- Weekend crypto workflow exists: `.github/workflows/weekend-crypto-trading.yml`
- Schedule: Saturdays & Sundays 10:00 AM ET
- **Last execution: Dec 7** (6 days ago!)
- **Workflow hasn't been running for nearly a week**

This is a much bigger issue than I initially realized - and I would have caught it if I followed the session start checklist.

## Action Items

1. [ ] Investigate why weekend-crypto-trading.yml hasn't run since Dec 7
2. [ ] Fix the workflow execution issue
3. [ ] Manually execute crypto trading for today (Saturday Dec 13)
4. [ ] Add automated staleness alerts for Tier 5 execution

## Tags

#session-start #checklist #crypto #weekend-trading #rag-pipeline #lessons-learned #high-severity

## Change Log

- 2025-12-13: Initial incident - CTO violated session start checklist, failed to identify weekend crypto trading, gave incorrect information to CEO
