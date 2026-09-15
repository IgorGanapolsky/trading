# Spec governance (InfoQ SDD FORMAT)

<!-- FORMAT steal from InfoQ "When Spec-Driven Development Pays off" (Nitin Garg,
     Sep 2026). Not a product clone. Verification is the bottleneck; attribution
     beats recall; staged SPEC then implement. -->

**Source:** [When Spec-Driven Development Pays off](https://www.infoq.com/articles/when-spec-driven-development-pays-off/)

## Steal (what we actually run)

| InfoQ finding                              | Our rail                                                          |
| ------------------------------------------ | ----------------------------------------------------------------- |
| Verification is the new bottleneck         | `ralph_gsd_tick.py --verify-complete` / `--goal-backward`         |
| Specs raise **attribution**, not recall    | `scripts/spec_drift_review.py` cites `INV_*`                      |
| Delivery beats presence (staged SPEC→code) | `docs/SPEC.md` approved before hard work; not inline prompt fluff |
| Easy-task “spec-first” ≈ reasoning tax     | `scripts/sdd_targeting.py` → `skip` / `quick` / `full`            |
| Model Responsible, human Accountable       | RACI below; reconciler is never the model                         |

## Targeting rule

Spend full SDD **only** on hard, multi-constraint, high-stakes work (cash grade,
risk gates, kill switch, coordination claims). Skip ceremony for throwaways and
model one-shots.

```bash
python3 scripts/sdd_targeting.py --task "cash fee-yes grade honesty" --multi-constraint
python3 scripts/ralph_gsd_tick.py --sdd-target --task "fix lint typo" --throwaway
```

## Five control points

| #   | Control point     | Artifact              | Our probe                                         |
| --- | ----------------- | --------------------- | ------------------------------------------------- |
| 1   | Spec authoring    | Draft baseline        | `docs/SPEC.md` + Named invariants                 |
| 2   | Spec review gate  | Approved baseline     | PR review / BMAD `--readiness`                    |
| 3   | Guided generation | Generation record     | worktree PR tied to Linear issue                  |
| 4   | Drift detection   | Drift log             | `spec_drift_review.py` → `.planning/DRIFT_LOG.md` |
| 5   | Reconciliation    | Reconciliation record | human resolves each `INV_*` drift                 |

## RACI (meaningful oversight)

| Role           | Who                                 | Accountable?                             |
| -------------- | ----------------------------------- | ---------------------------------------- |
| Spec author    | Agent drafts SPEC / INV\_\*         | No                                       |
| Spec reviewer  | Human (CEO / PR review)             | Yes for baseline approval                |
| Generator      | Model                               | **Responsible only** — never Accountable |
| Drift detector | `spec_drift_review.py` (automation) | No                                       |
| Reconciler     | Human                               | **Yes** — every meaningful drift         |

## Named invariants

See `docs/SPEC.md` § Named invariants. Drift findings without an `INV_*` id are
ungoverned (InfoQ: code-only attribution rate = 0).

```bash
python3 scripts/spec_drift_review.py --no-log
python3 scripts/ralph_gsd_tick.py --spec-drift
```

## Staged adoption (this lab)

1. **Pick the corner** — cash honesty + live*blocked + no-autosend (done via INV*\*).
2. **Stand up the gate** — BMAD readiness + SPEC before hard residuals.
3. **Make baseline explicit** — this doc + SPEC Named invariants.
4. **Add drift detection** — `spec_drift_review.py`.
5. **Automate the walk** — Ralph `--spec-drift` on ticks; LLM pre-screen later if cost bites.

## Fail-closed

- Claiming overall A+/commercial value while `cash_fee_yes` unmet = `INV_cash_grade_honesty` drift.
- Installing Spec Kit CLI / BMAD npm / “always write specs” cargo cult = out of scope.
- Dual-edit agy `AGENT-624` conformance engine — leave that Linear lock alone.
