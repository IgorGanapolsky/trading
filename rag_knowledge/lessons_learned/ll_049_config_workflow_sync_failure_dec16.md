# Lesson Learned #049: Config-Workflow Sync Failure - Disabled Features Still Running

**ID**: LL-049
**Date**: December 16, 2025
**Severity**: CRITICAL
**Category**: Configuration Management, Automation, Verification
**Impact**: Disabled features still running in production
**Decision By**: CTO (Claude)

## Prevention Rules

1. **Config-Workflow Sync Validation**: Always validate config matches workflow files
2. **Single Source of Truth**: Use one config file, not multiple
3. **Pre-Commit Check**: Add pre-commit hook to verify sync

---

## Executive Summary

**Crypto was "disabled" in system_state.json but STILL RUNNING in GitHub Actions** because config changes weren't propagated to workflow files.

## The Failure

| What Was Said | What Actually Happened |
|---------------|------------------------|
| "Crypto removed Dec 15" | Crypto trades executed Dec 13, 14, 15 |
| "Focus on options only" | Options stopped Dec 12, crypto continued |
| `tier5.enabled: false` | `ENABLE_CRYPTO_AGENT: 'true'` in workflow |

### Evidence

**system_state.json** (Dec 15):
```json
"tier5": {
    "name": "Crypto Strategy (DISABLED)",
    "enabled": false,
    "disabled_reason": "0% win rate"
}
```

**daily-trading.yml** (Dec 15 - STILL ENABLED):
```yaml
ENABLE_CRYPTO_AGENT: 'true'
CRYPTO_DAILY: 'true'
CRYPTO_DAILY_AMOUNT: '25.00'
```

## Root Cause Analysis

1. **No single source of truth** - Config in JSON, execution in YAML
2. **No validation** - Nothing checks if config matches workflow
3. **Manual sync required** - Humans forget, automation doesn't

## The Fix Applied

1. **Deleted crypto entirely** - 12 files, 4,870 lines removed
2. **Set workflow flags to false**:
```yaml
ENABLE_CRYPTO_AGENT: 'false'
CRYPTO_DAILY: 'false'
CRYPTO_DAILY_AMOUNT: '0'
```

## Prevention: Config-Workflow Sync Validator

### New Verification Required

Create `scripts/verify_config_workflow_sync.py`:
- Read `data/system_state.json` for strategy enabled/disabled status
- Parse `.github/workflows/*.yml` for corresponding env vars
- FAIL CI if mismatch detected

### Pre-Commit Hook

```bash
# .pre-commit-config.yaml addition
- repo: local
  hooks:
    - id: config-workflow-sync
      name: Verify config matches workflows
      entry: python scripts/verify_config_workflow_sync.py
      language: python
      pass_filenames: false
```

### CI Gate

```yaml
# .github/workflows/ci.yml addition
- name: Verify Config-Workflow Sync
  run: python scripts/verify_config_workflow_sync.py --strict
```

## Key Mappings to Validate

| system_state.json | Workflow Variable | Must Match |
|-------------------|-------------------|------------|
| `strategies.tier5.enabled` | `ENABLE_CRYPTO_AGENT` | ✅ |
| `strategies.options.enabled` | Options workflow exists | ✅ |
| `automation.github_actions_enabled` | Workflows not disabled | ✅ |

## The Bigger Lesson

> **If a feature is "disabled" in config but "enabled" in code, the CODE WINS.**

Config is documentation. Code is execution. They must be synchronized.

## Checklist for Future Config Changes

- [ ] Update system_state.json ✓ (done Dec 15)
- [ ] Update workflow YAML files ✗ (MISSED)
- [ ] Delete related code ✗ (MISSED until Dec 16)
- [ ] Run config-workflow sync validator ✗ (didn't exist)
- [ ] Verify in CI ✗ (no gate existed)

## Tags

`config-sync`, `workflow-validation`, `automation-gap`, `disabled-features`, `verification`

## Related Lessons

- LL_010: Dead Code and Dormant Systems
- LL_022: Options Not Automated
- LL_043: Crypto Removed
