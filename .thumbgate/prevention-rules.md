# Prevention Rules

Generated from negative feedback memories (time-weighted, half-life: 7d).

## general
- Recurrence count: 17 (weighted: 3.5)
- Rule: Keep every Stop/SubagentStop handler fail-open when stop_hook_active is true, persist CLAUDE_CODE_STOP_HOOK_BLOCK_CAP=50 for claude-yolo, clear only verified stale Ralph state, and smoke-test both recursive and normal stop paths.
- Latest mistake: MISTAKE: Claude Code used its default Stop hook block cap of 8, so the ninth consecutive block forced the turn to end even...

## Root Cause Categories
- guardrail_triggered: 34 failures

## Repeated Failure Constraints
- security:generic_assignment: 79 failures
- security:github_pat: 2 failures

## Auto-Review & Sandboxing Rules (Reviewer Agent)
- **Constraint:** `sandboxing:writable_roots` - Block any write action outside of `src/`, `tests/`, `data/`, `.claude/`, `scripts/`, or `.thumbgate/`.
- **Constraint:** `security:credential_protection` - Block any action reading or modifying `.env` or secret-carrying files.
- **Constraint:** `safety:ledger_backup` - Modifications to `data/system_state.json` or `data/trades.json` MUST be preceded by a backup in `data/backups/`.
- **Constraint:** `safety:circuit_breaker` - After 3 consecutive safety rejections, the agent must halt and request human intervention.
