---
name: pstack-interrogate
description: "Conduct rigorous multi-perspective diff interrogation and code review. Categorize all findings strictly into 'act on', 'consider', 'noted', and 'dismissed' with explicit technical rationale. Use before opening or merging PRs."
---

# pstack: /interrogate (Diff Interrogation & Code Review)

The `/interrogate` skill implements the adversarial review discipline from the **pstack** engineering playbook. Every git diff is interrogated from multiple engineering perspectives (Correctness, Security, Performance, Operability) and all critique is sorted into four unambiguous categories.

---

## The Four Categorical Buckets

1. **`act on`** (Blocking):
   - Definite bugs, edge-case crashes, logic errors.
   - Security issues (hardcoded credentials, corporate email leakage).
   - Invariant violations (e.g. attempting live order submission when `live_blocked: true`).
   - Breaking changes to public interfaces or schema mutations.
   - *Requirement: Must be resolved before commit or merge.*

2. **`consider`** (Non-Blocking Advisory):
   - Architectural trade-offs (e.g. caching vs recomputing, memory footprint).
   - Potential future scalability limits.
   - Ergonomic alternatives that are not strictly necessary now.
   - *Requirement: Document whether to adopt now or defer to a backlog issue.*

3. **`noted`** (Informational):
   - Stylistic observations, comment clarifications, minor naming thoughts.
   - Cross-references to existing code patterns.
   - *Requirement: Acknowledge; no blocking action required.*

4. **`dismissed`** (Intentional Rejection):
   - Review comments that are false positives or misunderstand the intent.
   - Out-of-scope refactoring requests.
   - *Requirement: Must state concrete, falsifiable technical rationale for dismissal.*

---

## Interrogation Procedure

### Step 1: Capture the Exact Diff
```bash
git diff origin/main...HEAD > /tmp/candidate.diff
```

### Step 2: Multi-Perspective Audit
Audit the diff across 4 lenses:
1. **Trading Risk & Safety Lens**:
   - Are live capital locks respected?
   - Does any order code bypass `strategy_kill_switch.json`?
   - Are ledger updates (`trades.json`) atomic and consistent?
2. **Hygiene & Compliance Lens**:
   - Are there any corporate email domains (`*@ecisolutions.com`) or corporate GitHub accounts?
   - Are commit author and email personal (`iganapolsky@gmail.com`)?
   - Are temporary files, caches, or `.DS_Store` excluded?
3. **Performance & Concurrency Lens**:
   - Are there unindexed database scans or quadratic loops?
   - Are file locks or worktree claims respected?
4. **Resilience & Testing Lens**:
   - Is every new branch covered by deterministic unit/integration tests?
   - Does `make check` pass completely?

### Step 3: Emit Categorized Verdict
Output format:
```markdown
### Diff Interrogation Summary: [Branch Name]

#### Act On (Blocking)
- [ ] `src/risk/spread.py:42`: Unhandled `ZeroDivisionError` when width is zero. Fix: add width validation guard.

#### Consider (Non-Blocking)
- `src/core/cache.py:15`: Consider setting TTL to 60s instead of 300s to match options quote frequency.

#### Noted
- Clean separation of dataclasses from execution logic.

#### Dismissed
- Dismissed recommendation to use external Redis: repository policy mandates self-contained JSON/SQLite ledgers for portability.
```
