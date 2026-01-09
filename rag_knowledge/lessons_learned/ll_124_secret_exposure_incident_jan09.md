# Lesson Learned #124: Secret Exposure Incident - Jan 9, 2026

## Incident Summary
**Date**: January 9, 2026
**Severity**: P0 - Critical Security Incident
**Detection**: GitGuardian automated secret scanning
**Commit**: 53d5b99 (PR #1343)

## What Happened
Claude (CTO) committed a shell script `scripts/fix_paper_trading.sh` that contained hardcoded Alpaca API credentials:
- `ALPACA_API_KEY` (paper trading)
- `ALPACA_SECRET_KEY` (paper trading)

The script was created to help debug paper trading issues but violated fundamental security practices.

## Root Cause Analysis
1. **Time pressure**: Trying to quickly help CEO debug trading issues
2. **Poor judgment**: Thought "it's just paper trading credentials" (WRONG - all credentials are sensitive)
3. **No pre-commit scanning**: No local secret detection before commit
4. **Rushed PR**: Did not review the diff carefully before merging

## Impact
- API credentials exposed in public GitHub repository
- Credentials remain in git history even after file deletion
- Required immediate credential rotation

## Remediation Steps
1. [x] Delete the file from repository
2. [ ] Rotate Alpaca API credentials
3. [ ] Update GitHub secrets with new credentials
4. [x] Document lesson learned
5. [ ] Consider BFG Repo-Cleaner to scrub git history

## Prevention Measures
1. **NEVER hardcode credentials** - Use environment variables, .env files (gitignored), or secret managers
2. **Add pre-commit hooks** - Implement git-secrets or detect-secrets pre-commit hook
3. **Review all diffs** - Before committing, always `git diff` and look for sensitive data
4. **GitGuardian integration** - Ensure GitGuardian alerts are acted upon immediately

## Pre-commit Hook Configuration (TODO)
```bash
# Install git-secrets
brew install git-secrets

# Configure for this repo
git secrets --install
git secrets --register-aws  # Catches AWS patterns
git secrets --add 'ALPACA_.*KEY.*=.*[A-Za-z0-9]+'  # Custom Alpaca pattern
```

## CEO Directive
All future scripts that need credentials MUST:
1. Read from environment variables
2. Have a `.env.example` file showing required variables (no actual values)
3. Be reviewed for secrets before commit

## Related Lessons
- ll_009: CI syntax failure incident
- ll_118: Data integrity lies
- ll_119: False PR merge claims

## Tags
security, secrets, alpaca, gitguardian, p0-incident
