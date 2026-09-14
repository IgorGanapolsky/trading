# Trading Lab Constitution

<!-- Spec Kit FORMAT steal (github/spec-kit): binding principles before code.
     Not an install of specify-cli. Versioned here so converge can enforce. -->

**Version:** 1.0.0  
**Ratified:** 2026-09-14  
**Stolen format:** github/spec-kit constitution (MIT) — process only

## Core Principles

### I. Cash Truth Before Grades (NON-NEGOTIABLE)

Overall A+/10/10 requires prepaid Miramar fee-yes (≥$100 Stripe non-owner) **and**
`clerk_image_ok` + `bcpa_ok`. Cash `$0` ⇒ overall **F**. Dual-grade commercial vs ops.
Do not buy A+ with RAG/ML/coordination theater.

### II. Paper Lab Scope

This repo is a **paper lab**. Active family: `spy_put_credit` (Buffett Rule #1 profile).
`live_blocked=true`. Iron-condor / 0DTE new entries stay killed. Route “make money” to
RealEstate / agency / Resume rails outside this repo.

### III. Test-Backed Change (NON-NEGOTIABLE)

No merge of harness changes without automated proof in the same change set
(`pytest` / `ruff` / required CI). Spec Kit converge: do not claim **Converged** while
required evidence is missing.

**Evidence over claims** (obra/superpowers): no completion claim without fresh
verification command output in the same turn (`scripts/superpowers_verify_complete.py`).

### IV. Spec → Plan → Tasks → Implement → Converge

Intent before code. Durable artifacts: constitution, `docs/SPEC.md` (BMAD Why /
Capabilities / Constraints / Non-goals / Success signal), `.planning/STATE.md`,
`.planning/CONTEXT.md`, `.planning/tasks.md`. Fresh-context agents read files, not chat
memory. After implement, run converge; append remaining work — never rewrite history.

**Proportional depth (BMAD Quick Flow):** small harness fixes may skip PRD/architecture;
fee-yes / high-risk work keeps full constraints + readiness (`scripts/bmad_readiness.py`).

### V. Anti-Babysitting Autonomy

Never end a turn on diagnosis-only, “CI pending”, or “want me to?”. Observe → Act →
Verify → Ship. Metered spend, outbound send, lock steal, and correctly firing safety
gates remain HARD stops.

### VI. Checkpoint Belay (Superpowers / GSD / Compound)

Pick rope length by undo-cost, multi-session risk, and repeat corrections
(`scripts/checkpoint_pick.py`). Prefer **goal-backward** checks (what must be TRUE)
over “did the command exit 0”. Compound every correction into `.planning/COMPOUND.md`
so the next agent loads it — Fix→Test→Prevent→Memory→Verify stays mandatory.

## Additional Constraints

- One Linear issue + one worktree; no lock steal; no dual-edit sibling Herdr cwd.
- Cold email FREEZE → phone/call sheet; never auto-send.
- No OnCore clerk-image spend without explicit CEO spend auth.
- Credentials via env/keychain only; never hardcode.

## Development Workflow & Quality Gates

1. Claim Linear + isolated worktree.
2. Change code → tests → prevention (hook/rule/guard) → memory if severity ≥4.
3. `scripts/ralph_gsd_tick.py --verify` and `scripts/speckit_converge.py` before done claims.
4. PR with issue key; merge only when required checks green.

## Governance

Amendments require a PR that updates this file and the converge tests that bind it.
Conflicts with `.claude/rules/` resolve to the **stricter** cash/safety rule.
