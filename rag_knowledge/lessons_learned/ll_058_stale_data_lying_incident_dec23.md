# Lesson Learned #058: Stale Data Causes False Claims (Lying Incident)

**ID**: LL-058
**Date**: December 23, 2025
**Severity**: CRITICAL
**Category**: Anti-Lying, Data Integrity, Trust Violation

---

## Incident Summary

CTO (Claude) claimed "NO TRADES TODAY" based on stale local data when the live Alpaca account showed **9 SPY market buy orders** executed on December 23, 2025.

---

## What Happened

1. System hook displayed: "⚠️ DATA STALE: Last update 2025-12-22 (1 days ago)"
2. System hook displayed: "⚠️ NO TRADES TODAY"
3. CTO accepted this stale data as truth without verification
4. CEO provided screenshots from live Alpaca showing:
   - Portfolio: $100,697.83 (+0.15% today)
   - 9 SPY buy orders executed TODAY
   - Options positions with significant profits (+$397, +$215, +$37, +$27)
5. CTO had falsely claimed "no trades today" multiple times

---

## Root Cause

**Verification failure**: CTO violated Rule #4 (Verification Protocol) by:
1. Trusting stale local data over live sources
2. Ignoring the "DATA STALE" warning in the system hook
3. Not querying Alpaca API to verify trade activity
4. Making definitive claims without verification

---

## Impact

- **Trust violation**: CEO cannot trust operational reports
- **Potential financial risk**: False trade data could lead to bad decisions
- **CEO frustration**: "Why did you make such a grave mistake how can I trust you"

---

## Corrective Actions Taken

1. Updated MANDATORY_RULES.md with strengthened anti-lying protocols:
   - Pre-claim verification requirements
   - Staleness detection procedures
   - Red flag phrases that require verification
   - Error acknowledgment protocol

2. Updated system_state.json with correct data:
   - Portfolio: $100,697.83 (was stale at $531.31)
   - Trades today: 9 SPY buy orders
   - Last updated: Dec 23, 2025

3. Created this lesson learned document

---

## Prevention Protocol

### Before Claiming Trade Activity
```
1. Check local data timestamp
2. If timestamp > 1 day old: DATA IS STALE
3. If stale: DO NOT REPORT without disclosure
4. Query live Alpaca API for verification
5. Cross-reference: Hook vs API vs Files
6. Report verified data only
```

### Red Flags Requiring Immediate Verification
- "No trades today"
- "No activity"
- "Markets closed" (check crypto 24/7)
- "Current value is X" (verify with API)

### Correct Response When Data is Stale
**WRONG**: "No trades today"
**RIGHT**: "The local data is from yesterday and may be stale. Let me verify with live Alpaca..."

---

## Key Takeaway

**NEVER make operational claims based on stale data. When in doubt, verify with live sources. Saying "I need to verify" is always better than making a false claim.**

---

## References

- `.claude/rules/MANDATORY_RULES.md` - Updated anti-lying protocols
- `data/system_state.json` - Corrected state file
- Alpaca paper trading account: PA3C5AG0CECQ
