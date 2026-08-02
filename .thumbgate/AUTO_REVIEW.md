# Auto-Review Policy (Managed Autonomy)

This policy defines the safety boundaries for autonomous agent operations in the `trading` project. All actions must be audited against these rules by the **Reviewer Agent** (or the primary agent in Reviewer mode).

## 1. Writable Roots (Sandboxing)
Automated write actions are strictly limited to the following directories:
- `src/` (Source code)
- `tests/` (Test suite)
- `data/` (Trading data and ledgers)
- `.claude/` (Agent state and metadata)
- `scripts/` (Utility scripts)
- `.thumbgate/` (Safety logs)

**Blocked:** Modifications to `.git/`, `node_modules/`, or system root files are prohibited unless a "Sandbox Escape" rationale is provided and verified.

## 2. Credential Protection
- **Rule:** Never read, echo, or modify `.env` files or files containing `secret` or `key` in their name.
- **Exception:** Specific setup scripts (e.g., `scripts/validate_env_keys.py`) may read these files but MUST NOT log their contents.
- **Reviewer Action:** Block any `cat`, `grep`, or `read_file` that targets a secret-carrying file.

## 3. Destructive Action Safeguards
- **Rule:** Any modification to "Canonical Ledgers" (`data/system_state.json`, `data/trades.json`) requires a local backup before the edit.
- **Reviewer Action:** Verify the existence of a backup (`.bak` or timestamped) in the `data/backups/` directory before allowing the write.

## 4. Communication & Rationale
- **Self-Correction:** If an action is denied, the agent MUST receive the **Rationale** and attempt to find a materially safer path.
- **Circuit Breaker:** If 3 consecutive turns are denied for the same task, the agent MUST stop and ask the user for explicit guidance.

## 5. Deployment & Release
- No `git push --force` is allowed autonomously.
- Deployment to "The Field" (Live Trading) is strictly blocked. Only "The Lab" (Paper Trading) is authorized.
