---
title: "Lesson Learned #119: Paper Trading Automation Dead for 23 Days"
date: 2026-01-08
severity: CRITICAL
category: automation
tags: [github-actions, secrets, paper-trading, rag]
related_incidents: [ll_117, ll_109]
---

# Lesson Learned #119: Paper Trading Automation Dead for 23 Days - Secret Inconsistency + GitHub Actions Issue

**Date**: January 8, 2026
**Severity**: CRITICAL
**Status**: FIXED (workflow secret), INVESTIGATION NEEDED (GitHub Actions cron)

## 🚨 INCIDENT SUMMARY

CEO discovered that both paper trading AND RAG systems were completely broken:

1. **Paper Trading Automation**: Last execution Dec 16, 2025 (23 days ago!)
   - Cron schedule should run daily at 9:35 AM ET (Mon-Fri)
   - No trades executed Jan 7-8 despite being trading days
   - Jan 6 trades were MANUAL triggers (not automatic)

2. **RAG Sync**: `sync_mode: "skipped_no_keys"` - not syncing to Vertex AI
   - Dialogflow webhook showing 0 input/output parameters

3. **Alpaca Secret Inconsistency**: One step still used old credentials
   - Most workflow steps: `ALPACA_PAPER_TRADING_5K_API_KEY` (correct)
   - Line 286-287: `ALPACA_PAPER_TRADING_API_KEY` (old - WRONG!)

## 📊 EVIDENCE

```json
{
  "automation": {
    "github_actions_enabled": true,
    "workflow_status": "NEEDS_VERIFICATION",
    "last_execution_attempt": "2025-12-16T19:27:00",
    "last_successful_execution": "2025-12-15T18:18:15",
    "incident_jan07_2026": "No trade file created today despite workflow being scheduled"
  },
  "meta": {
    "last_sync": "2026-01-08T19:12:19.803783",
    "sync_mode": "skipped_no_keys"
  },
  "paper_account": {
    "current_equity": 5000.0,
    "last_sync": "2026-01-07T17:15:00",
    "sync_source": "CEO reset paper account Jan 7 2026"
  },
  "trades": {
    "last_trade_date": "2026-01-06",
    "total_trades_today": 2
  }
}
```

**Workflow Schedule**: `cron: '35 13,14 * * 1-5'` (should run at 9:35 AM ET daily)

**Today (Jan 8, 2026)**: Thursday
- Should have run at 14:35 UTC (9:35 AM ET)
- Current time: 23:52 UTC
- **Result: NO EXECUTION** (9.5 hours past scheduled time)

## 🔍 ROOT CAUSE ANALYSIS

### Issue #1: Secret Inconsistency (FIXED)

Commit `78e42eb` ("fix(ci): Update workflows to use $5K paper trading account") updated most of the workflow to use the new $5K paper account secrets, but **missed line 286-287** in the "protect-existing-positions" job.

**Impact**:
- Secret validation may have failed (blocking execution)
- If old secrets were deleted, step would fail (but `continue-on-error: true`)
- Workflow status shows "NEEDS_VERIFICATION" since Dec 16

### Issue #2: GitHub Actions Cron Not Triggering (INVESTIGATION NEEDED)

The workflow hasn't run **automatically** since Dec 16, despite:
- Cron schedule being correct (`35 13,14 * * 1-5`)
- Recent commits to the repo (Jan 1-8)
- `github_actions_enabled: true` in system state

**Possible causes**:
1. **Workflow disabled** in GitHub Actions settings (needs manual re-enable)
2. **Secret validation failing** (blocking execution silently)
3. **Branch mismatch** (workflow not on default branch) - UNLIKELY
4. **GitHub disabled cron** after 60 days repo inactivity - UNLIKELY (had commits)

### Issue #3: RAG Sync Broken

`sync_mode: "skipped_no_keys"` indicates missing GCP credentials:
- Required: `GCP_SA_KEY` (service account JSON) OR `GOOGLE_API_KEY`
- Neither is available in GitHub secrets (or sandbox)
- Workflow checks for these at lines 183-184, 1557

**Impact on Dialogflow**:
- Webhook deployed to Cloud Run
- Returns 0 input/output parameters (not receiving query properly)
- May need Dialogflow agent configuration fix

## ✅ FIX APPLIED

### 1. Secret Inconsistency (COMPLETED)

**File**: `.github/workflows/daily-trading.yml`
**Lines**: 286-287

**Before**:
```yaml
ALPACA_API_KEY: ${{ github.event.inputs.trading_mode == 'live' && secrets.ALPACA_BROKERAGE_TRADING_API_KEY || secrets.ALPACA_PAPER_TRADING_API_KEY }}
ALPACA_SECRET_KEY: ${{ github.event.inputs.trading_mode == 'live' && secrets.ALPACA_BROKERAGE_TRADING_API_SECRET || secrets.ALPACA_PAPER_TRADING_API_SECRET }}
```

**After**:
```yaml
ALPACA_API_KEY: ${{ github.event.inputs.trading_mode == 'live' && secrets.ALPACA_BROKERAGE_TRADING_API_KEY || secrets.ALPACA_PAPER_TRADING_5K_API_KEY }}
ALPACA_SECRET_KEY: ${{ github.event.inputs.trading_mode == 'live' && secrets.ALPACA_BROKERAGE_TRADING_API_SECRET || secrets.ALPACA_PAPER_TRADING_5K_API_SECRET }}
```

**Commit**: `604ce15` ("fix(ci): Update protect-existing-positions to use 5K paper secret")

### 2. Required Actions (CEO MUST DO)

#### A. Check GitHub Actions Status
1. Go to: https://github.com/IgorGanapolsky/trading/actions/workflows/daily-trading.yml
2. Check if workflow is **DISABLED** (look for "Disabled" badge)
3. If disabled, click **"Enable workflow"**
4. Check workflow run history - when was last run?

#### B. Add Missing GCP Secrets (for RAG sync)
1. Go to: https://github.com/IgorGanapolsky/trading/settings/secrets/actions
2. Add **GCP_SA_KEY** (service account JSON) OR **GOOGLE_API_KEY**
3. Required for:
   - Vertex AI RAG sync (`scripts/sync_trades_to_rag.py`)
   - Pre-trade RAG query (`scripts/query_vertex_rag.py`)

#### C. Manually Trigger Workflow (to test)
1. Go to: https://github.com/IgorGanapolsky/trading/actions/workflows/daily-trading.yml
2. Click **"Run workflow"**
3. Select branch: `main` (or `claude/fix-paper-trading-rag-rpaMF` to test this fix)
4. Trading mode: `paper`
5. Force trade: `false`
6. Click **"Run workflow"**
7. **WATCH THE RUN** - check for errors, verify trades execute

#### D. Verify Dialogflow Webhook
1. Test webhook at: https://trading-dialogflow-webhook-cqlewkvzdq-uc.a.run.app/test
2. Check if it returns lessons (should show `results_count > 0`)
3. Test portfolio query: https://trading-dialogflow-webhook-cqlewkvzdq-uc.a.run.app/test-trades
4. If both work, check Dialogflow agent configuration (not webhook code)

## 📝 LESSONS LEARNED

### 1. **Incomplete Secret Migration is Silent**
When updating secrets across a workflow, a single missed reference can break the system silently. The `continue-on-error: true` flag masked the failure.

**Prevention**:
- Use grep to verify ALL secret references: `grep -n "OLD_SECRET_NAME" workflow.yml`
- After secret migrations, run full workflow manually to verify
- Add CI check to detect inconsistent secret usage

### 2. **GitHub Actions Cron Can Silently Fail**
Scheduled workflows can stop running without obvious error messages. The last execution was 23 days ago, but system_state.json still showed `github_actions_enabled: true`.

**Detection**:
- Monitor `automation.last_execution_attempt` in system_state.json
- Alert if last execution > 2 days old (for daily workflows)
- Add workflow run monitoring (use GitHub API to check status)

### 3. **Multi-System Breakage Cascades**
Paper trading AND RAG both broke, compounding the visibility problem. If RAG was working, we could have queried for lessons about "why no trades."

**Prevention**:
- Systems should have independent health checks
- Critical systems (trading, RAG, monitoring) must not share single points of failure
- Add daily "heartbeat" check that alerts if ANY core system is down

### 4. **Trust But Verify - Even system_state.json**
The system state file showed `github_actions_enabled: true` but the workflow wasn't actually running. The file reflects **configuration**, not **actual execution status**.

**Fix**:
- Add "last_github_actions_run" timestamp (fetch from GitHub API)
- Compare configured state vs actual runtime state
- Alert on mismatch

## 🎯 ACTION ITEMS

- [x] Fix secret inconsistency in workflow (line 286-287)
- [ ] CEO: Check if GitHub Actions workflow is disabled
- [ ] CEO: Add GCP_SA_KEY or GOOGLE_API_KEY secret
- [ ] CEO: Manually trigger workflow to test fix
- [ ] CEO: Verify Dialogflow webhook is working
- [ ] Add workflow run monitoring (GitHub API polling)
- [ ] Add health check for "days since last trade" (alert if > 2)
- [ ] Create grep check for secret consistency in CI

## 📚 RELATED LESSONS

- **ll_117**: ChromaDB Removal Caused 2-Day Trading Gap (Dec 2025)
- **ll_109**: Bidirectional RAG Learning (Jan 7, 2026)
- **ll_092**: Compounding Strategy Mandatory (capital requirements)
- **ll_088**: Verification Violation - Claimed Blog Updated Without CEO Confirmation

## 🔗 REFERENCES

- Commit 78e42eb: "fix(ci): Update workflows to use $5K paper trading account"
- Commit 604ce15: "fix(ci): Update protect-existing-positions to use 5K paper secret"
- Workflow: `.github/workflows/daily-trading.yml`
- System state: `data/system_state.json`
- RAG sync script: `scripts/sync_trades_to_rag.py`

---

**CRITICAL**: This lesson demonstrates the importance of:
1. **Complete secret migrations** (grep verification)
2. **Active monitoring** (not just configuration files)
3. **Independent system health checks** (cascading failures are hard to debug)
4. **Manual testing after changes** (don't assume CI will catch everything)
