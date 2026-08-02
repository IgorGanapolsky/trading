# LL-318: CTO Session - Wrong Repo Confusion & RAG Query Protocol

**Date**: January 26, 2026
**Category**: Process / CTO Protocol
**Severity**: MEDIUM
**Session**: claude/daily-revenue-tracking-9j8nl

## What Happened

1. CEO asked "How much money did we make today?"
2. CTO (Claude) was working in `ai-promo-agent` repo instead of `trading` repo
3. Built revenue tracking system in wrong repo (no Alpaca secrets there)
4. Wasted time debugging "broken" credentials that were actually in different repo
5. CEO had to correct: "The fucking alpaca credentials are in GitHub!!!" pointing to `trading` repo

## Root Cause

- CTO did not follow Session Start Protocol from CLAUDE.md
- Did not query RAG at session start
- Did not verify which repo contains trading infrastructure
- Assumed `ai-promo-agent` was the trading system (it's just CI/CD infrastructure)

## Lessons Learned

### 1. Always Query RAG First

Before ANY work, query RAG for:

- Current system state
- Active repos and their purposes
- Recent lessons that may be relevant

### 2. Repo Responsibilities

| Repo             | Purpose                              | Has Alpaca? |
| ---------------- | ------------------------------------ | ----------- |
| `trading`        | Main trading system, strategies, RAG | ✅ YES      |
| `ai-promo-agent` | CI/CD, monitoring, alerts            | ❌ NO       |

### 3. Revenue Data Location

- `trading` repo: `data/system_state.json`
- Contains: equity, P&L, positions, trade history
- Updated by: `sync-alpaca-status.yml` workflow

### 4. North Star Reminder

**Goal**: $6K/month after-tax (Financial Independence)
**Strategy**: Phil Town Rule #1 + Iron Condors
**Current**: $29,986.20 equity, Day 5 of paper validation

## Corrective Actions

1. ✅ Switched to correct repo (`trading`)
2. ✅ Read RAG (Phil Town Rule #1, Financial Independence Roadmap)
3. ✅ Retrieved actual P&L from `data/system_state.json`
4. ✅ Logged this lesson to prevent recurrence

## Session Metrics

| Metric      | Value               |
| ----------- | ------------------- |
| Today's P&L | +$32.78             |
| Total P&L   | -$13.80 (-0.05%)    |
| Positions   | 4 (SPY Iron Condor) |
| Win Rate    | 0% (no closes yet)  |

## Protocol Update

**CTO Session Start Checklist:**

- [ ] Read CLAUDE.md
- [ ] Query RAG for recent lessons
- [ ] Verify working in `trading` repo for trading tasks
- [ ] Check `data/system_state.json` for current status
- [ ] Confirm North Star: $6K/month after-tax

## Tags

`cto-protocol`, `wrong-repo`, `rag-query`, `process-improvement`
