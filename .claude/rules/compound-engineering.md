# Compound Engineering Protocol

Every change must include all 5 steps. No exceptions.

## The 5-Step Protocol

### 1. Fix

The actual code change. Minimum viable — no over-engineering.

### 2. Test

Automated proof it works:

```bash
pytest tests/ -x --tb=short  # Run relevant tests
ruff check src/               # Lint passes
```

### 3. Prevention

Mechanism to prevent recurrence. Pick one:

- **Rule**: Add to `.claude/rules/` if pattern-based
- **Hook**: Add check to session-start or pre-commit if automated
- **Guard**: Add validation in code if runtime-detectable

### 4. Memory

Record the lesson:

- Update RLHF feedback log with context
- If critical (severity >= 4): add to `rag_knowledge/lessons_learned/`
- Thompson model auto-updates via hooks

### 5. Verify

Evidence of success — not just "done":

- Show command output proving the fix works
- Confirm CI passes on the PR
- Read back state after mutation

## Daily Checklist

```bash
ruff check src/ && pytest tests/ -x --tb=short && python scripts/system_health_check.py
```

## Mandatory Completion Gate

Before claiming ANY task is done, verify ALL 5 steps are addressed:

```
[ ] 1. FIX — code change committed
[ ] 2. TEST — pytest passes, new tests cover the fix
[ ] 3. PREVENT — CI check, hook, or guard added that blocks recurrence
[ ] 4. MEMORY — lesson recorded if severity >= 4
[ ] 5. VERIFY — CI green, evidence shown, state confirmed
```

**If step 3 (Prevention) is missing, the task is NOT complete.**
Prevention means: if someone writes new code that reintroduces this bug,
something automated (CI, hook, or runtime guard) will catch it BEFORE
it reaches production. A fix without prevention is a fix that will recur.

## Anti-Patterns

- Claiming "fixed" without verification evidence
- Fix without test (will break again)
- Fix without prevention (will recur)
- Fix without memory (won't learn)
- Over-engineering the prevention (simple > complex)
- **Shipping the fix and adding prevention as an afterthought when the CEO asks** (Feb 6, 2026 lesson)

## Trading-Specific Applications

- Trade execution failure → Fix + backtest + stop-loss rule + RAG lesson + P/L verification
- CI breakage → Fix + test + pre-commit hook + lesson + green CI screenshot
- Data integrity issue → Fix + validation test + monitoring alert + LL entry + data verification
