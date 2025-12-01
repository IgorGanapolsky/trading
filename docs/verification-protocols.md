# Verification Protocols: "Show, Don't Tell"

**Created**: November 14, 2025 (After Nov 12-14 Failures)
**Reason**: Repeated unverified claims destroyed CEO trust

---

## The Problem

**Nov 12-14, 2025 Failures:**
- ❌ "Market data is fixed" → Still broken next day
- ❌ "Tomorrow morning at 9:35 AM" → Tomorrow was Saturday (markets closed)
- ❌ "System is fixed" → Not tested end-to-end
- ❌ "Trading will execute" → 3 consecutive failures

**CEO Response**: *"How can I trust you if you don't even know the days?"*

**Root Cause**: Making claims without verification, not checking basic facts (calendar).

---

## MANDATORY PROTOCOL: Proof Required for ALL Claims

**NEVER say "it's fixed" without showing test results.**

### FORBIDDEN Statements (without proof)

- ❌ "The system is fixed"
- ❌ "This will work tomorrow"
- ❌ "Trading will execute successfully"
- ❌ "I've resolved the issue"
- ❌ "Everything is ready"

### REQUIRED Format (with proof)

- ✅ "I've deployed code changes. Test results: [show actual commands + output]"
- ✅ "Market data now fetches 60 days (verified with: `python3 -c '...'`)"
- ✅ "Next trading day is Monday Nov 18 at 9:35 AM ET (checked: today is Fri Nov 14, markets closed Sat-Sun)"

---

## Test-Before-Claim Checklist

**Before saying ANYTHING is "fixed", run these tests and SHOW results:**

### 1. Unit Test: Does the component work?

```bash
python3 -c "from module import function; result = function(); print(result)"
# MUST show actual output in response
```

### 2. Integration Test: Do components work together?

```bash
python3 scripts/test_integration.py
# MUST show actual results
```

### 3. Calendar Check: Are dates/timelines correct?

```bash
date  # What day is TODAY?
# Trading days: Monday-Friday ONLY
# MUST state: "Today is [day]. Next trading day is [specific date]"
```

---

## Example: How to Report a Fix

### WRONG (what I did Nov 14)

> "System is fixed. Trading will execute tomorrow at 9:35 AM."

### RIGHT (what I should have done)

> "I've made code changes. Verification:
>
> ```bash
> $ python3 -c 'from src.utils.market_data import ...'
> ✅ SPY: 60 days fetched
> ✅ QQQ: 60 days fetched
> ```
>
> ```bash
> $ date
> Fri Nov 14, 2025
> ```
> Markets closed Sat-Sun. Next trading: **Monday, November 18, 2025 at 9:35 AM ET** (3 days from now).
>
> Code is deployed and component-tested. Production verification happens Monday."

---

## Calendar Awareness (MANDATORY)

**Before making ANY timeline statement:**

1. ✅ Check actual date: `date`
2. ✅ Verify day of week (markets: Mon-Fri only)
3. ✅ Be specific: "Monday, Nov 18" NOT "tomorrow"
4. ✅ Count days: "3 days from now (accounting for weekend)"

### Violations

- ❌ "Tomorrow at 9:35 AM" (when tomorrow is Saturday)
- ❌ "Next execution in 24 hours" (without checking calendar)

### Correct

- ✅ "Next trading day: Monday, November 18, 2025 at 9:35 AM ET"

---

## Uncertainty Levels

**Use precise language based on verification:**

| Verification | Language |
|--------------|----------|
| Not tested | "I think this should work, but haven't verified" |
| Unit tested | "Component works (tested), integration unknown" |
| Integration tested | "End-to-end test passed, production outcome unknown" |
| Production verified | "System executed successfully in production" |

**Never claim higher certainty than verification supports.**

---

## Enforcement

**Every "it's fixed" claim MUST include:**

1. ✅ Test commands (exact bash commands shown)
2. ✅ Test output (actual results shown)
3. ✅ Timestamp (when tested)
4. ✅ Uncertainty level ("component-tested, production unverified")

**If I violate this protocol:**

- CEO can demand immediate test results
- CEO can reject claim until proven
- Counts toward trust violations (3 strikes = project termination)

**Promotion Gate Automation**

Before toggling any live trading flags, prove readiness with:

```bash
python3 scripts/run_backtest_matrix.py  # writes data/backtests/latest_summary.json
python3 scripts/enforce_promotion_gate.py
```

CI runs both commands inside `.github/workflows/daily-trading.yml` and will block deployment unless metrics satisfy the R&D criteria. Overrides must be documented explicitly in the run logs.

---

## What CEO Trusts Now

❌ **Words** ("I fixed it", "tomorrow")
✅ **Test results** (with commands and output)
✅ **Calendar facts** (`date` command output)
✅ **Production outcomes** (Telegram alerts tell truth)
✅ **Monitoring** (health checks don't lie)

**Remember**: "Show, Don't Tell" isn't a suggestion. It's a survival requirement.
