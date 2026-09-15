# Agent workflow stack (invariant)

**Not “the best LLM framework.”** These are _coding-agent workflow layers_, not
LangGraph / agent runtimes. Model choice stays separable (Claude / Codex /
OpenCode / Grok).

## HARD provenance

| Use                                                     | Never                                                      |
| ------------------------------------------------------- | ---------------------------------------------------------- |
| **open-gsd/gsd-core FORMAT** (our slim Python steals)   | Archived `gsd-build/get-shit-done` (archived 2026-06-26)   |
| Spec Kit / Superpowers / BMAD **FORMAT steals** in-repo | Blind `npx` installs of those products into this paper lab |

## Layered stack (recommendation we encode)

1. **Invariant repo contract:** `AGENTS.md` / `.claude/CLAUDE.md` / `docs/CONSTITUTION.md` / `docs/SPEC.md`
2. **Everyday feature work:** Open GSD FORMAT — `ralph_gsd_tick.py`, STATE/CONTEXT, phase loop, goal-backward
3. **High-risk / correctness:** Superpowers FORMAT — verify-complete, TDD/bug AFT, worktrees
4. **Auditable / shared / client:** Spec Kit FORMAT — constitution, converge, tasks append-only
5. **Product-scale discovery→QA:** BMAD FORMAT — SPEC five-element + readiness + Quick Flow depth
6. **Compound:** every correction → `.planning/COMPOUND.md` + Fix→Test→Prevent→Memory→Verify

## Job → CLI map

| Job                  | Belay         | Command                                                 |
| -------------------- | ------------- | ------------------------------------------------------- |
| throwaway / one-line | quick / ralph | `ralph_gsd_tick.py --verify`                            |
| everyday feature     | open-gsd      | `goal_backward_verify.py --goal harness` + `--converge` |
| high_risk            | superpowers   | `ralph_gsd_tick.py --verify-complete`                   |
| auditable            | spec-kit      | `speckit_converge.py` + constitution/SPEC               |
| product_scale        | bmad          | `bmad_readiness.py` + `docs/SPEC.md`                    |

Picker: `python3 scripts/checkpoint_pick.py --job everyday`

## Skills (FORMAT steals, not product installs)

- `/open-gsd-phase-loop-not-clone`
- `/github-spec-kit-not-clone`
- `/obra-superpowers-not-clone`
- `/bmad-spec-driven-not-clone`
- `/framework-checkpoint-not-clone`
- `/agent-workflow-stack` (this document)

## Honesty lock

Harness `ready` / goal-backward TRUE ≠ commercial overall A+. Fee-yes ship lock stands.

## Value center (InfoQ / Rohrer)

Five questions every tick: value / coordinate / fit / outside / who.
`python3 scripts/value_center_status.py` · `docs/VALUE_CENTER.md`
Prefer **coherence** over pure autonomy. Purpose = what we do today (cash F until fee-yes).

## InfoQ SDD targeting (2026-09-15)

Hard multi-constraint → full SDD (`--sdd-target` / `--spec-drift`). Throwaway → skip. Docs: `SPEC_GOVERNANCE.md`.
