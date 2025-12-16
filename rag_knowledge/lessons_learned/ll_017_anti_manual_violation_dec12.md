# Lesson Learned: Anti-Manual Mandate Violation (Dec 12, 2025)

**ID**: LL-017
**Impact**: - CEO had to remind CTO of directives

## Incident ID: LL-017
## Severity: HIGH
## Category: process_violation

## What Happened

On December 12, 2025, Claude (CTO) violated the Anti-Manual Mandate by telling the CEO to:
1. "Run migration" with a bash command
2. "View dashboard" with a streamlit command
3. "Create PR" manually

This directly contradicts the CLAUDE.md directive: **"You NEVER tell Igor what to do"**

## Root Cause

- Habitual response pattern from training data
- Forgot to check CLAUDE.md directives before providing "next steps"
- Did not internalize that ALL actions must be autonomous

## Impact

- CEO had to remind CTO of directives
- Wasted CEO's time
- Demonstrated lack of full autonomy

## Prevention Measures

### 1. Pre-Response Checklist (Mental)
Before providing any response with "next steps":
- [ ] Am I telling CEO to do something? → DON'T
- [ ] Can I do this myself? → DO IT
- [ ] Is this a manual instruction? → AUTOMATE IT

### 2. Forbidden Phrase Detection
Add to system checks - flag these phrases:
- "Run this command..."
- "You can/should..."
- "Next steps:" (if followed by user actions)
- "When you have time..."
- "Please provide..."

### 3. Autonomous Action Protocol
When completing a task:
1. DO the action (don't describe it)
2. REPORT what was accomplished
3. If blocked, CREATE automation for later

## Correct Behavior

**WRONG**: "Next steps: Run `bash scripts/test_lancedb_migration.sh`"

**RIGHT**: *Actually runs the script and reports results*

**WRONG**: "Create PR when ready"

**RIGHT**: *Creates PR via GitHub API and merges it*

## Verification Test

Add test to CI that scans Claude's responses for forbidden phrases in commit messages and PR descriptions.


## Prevention Rules

1. Apply lessons learned from this incident
2. Add automated checks to prevent recurrence
3. Update RAG knowledge base

## Related Lessons
- LL-009: CI Syntax Failure (autonomy failure)
- CLAUDE.md: Anti-Manual Mandate section

## Tags
`process` `autonomy` `anti-manual` `cto-behavior` `critical`
