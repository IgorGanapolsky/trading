# Session Start Checklist (Mandatory)

## 1. Daily P/L Report (REQUIRED EVERY SESSION)

### Format
```
📊 Daily Status Report - [DATE]

**Alpaca Paper 5K Account:**
| Metric | Value |
|--------|-------|
| Equity | $X,XXX.XX |
| Today's P/L | +/-$XX.XX |
| Total P/L | +/-$XX.XX (X.XX%) |

**Why we made/lost money today (1 sentence):**
> [REASON - e.g., "SPY dropped 0.5%, increasing our long put value by $36"]

**Cross-System Verification:**
- Alpaca (source): $X,XXX.XX
- system_state.json: ✅/❌
- Dialogflow: ✅/❌
- GitHub Pages: ✅/❌
```

### Data Sources
1. Query Alpaca API directly (or use cached system_state.json)
2. Query Dialogflow webhook: `curl https://trading-dialogflow-webhook-cqlewkvzdq-uc.a.run.app/test-readiness`
3. Verify GitHub Pages index.md matches

### P/L Reason Guidelines
- **One sentence max**
- Include the **primary driver** (which position moved most)
- Include **direction** (SPY up/down, IV expansion/contraction)
- Example reasons:
  - "SPY rallied 1.2%, causing our short puts to decay faster (+$45 theta)"
  - "IV crush after Fed meeting reduced our long put value (-$28)"
  - "Credit spread hit 50% profit target, closed for +$32"

---

## 2. System Verification

- [ ] Check CI status on main
- [ ] Review open PRs
- [ ] Check for orphan branches
- [ ] Verify dashboards match Alpaca

---

## 3. Deferred Items

Track items that need attention but aren't blocking:
1. Close excess positions (6 → 4 legs) - Workflow dispatched, awaiting execution
2. Sync system_state.json - Data is 21h stale, sync workflow triggered

---

## 4. Ralph Mode Status

- Iteration: 10/100
- Current PRD tasks remaining: 0 (all passing)
- Last completed task: T006
- Last updated: 2026-01-20 18:18 UTC
