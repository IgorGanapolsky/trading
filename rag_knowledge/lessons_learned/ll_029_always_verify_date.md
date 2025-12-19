# LL-029: ALWAYS Verify Current Date Before Reporting

**ID**: LL-029

**Date**: 2025-12-14
**Severity**: CRITICAL
**Category**: Verification
**Impact**: User trust, data accuracy

## The Failure

Claude reported Saturday's (Dec 13) trades as "today" when it was actually Sunday (Dec 14). This caused:
1. Incorrect P/L reporting
2. User frustration and loss of trust
3. Missed that today's scheduled trade didn't execute

## Root Cause

1. Did not check actual system date before answering
2. Assumed file dates matched current date
3. Did not verify hook output ("Next Trade: Dec 15" was wrong)

## Prevention Rules

### Before ANY date-related statement:
```bash
# ALWAYS run this first
echo "Today is: $(date '+%A, %B %d, %Y')"
```

### Check trade dates match:
```bash
# Verify trades file is for TODAY
ls data/trades_$(date +%Y-%m-%d).json
```

### Verify hook output makes sense:
- If today is Sunday, next trade should be TODAY (weekend crypto)
- If today is Saturday, next trade should be TODAY (weekend crypto)
- If today is weekday, next trade should be TODAY at 9:35 AM

## Session Start Checklist (UPDATED)

```bash
# Step 0: VERIFY DATE FIRST
echo "Today is: $(date '+%A, %B %d, %Y')"

# Step 1: Get bearings
cat claude-progress.txt
...
```

## Tags

#critical #verification #trust #dates #never-again
