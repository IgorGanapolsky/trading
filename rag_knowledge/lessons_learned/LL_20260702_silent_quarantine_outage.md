# LL-2026-07-02 — Silent quarantine blocked ALL validation entries for 2 weeks

**Severity: 5 (system stopped trading while reporting green)**

## What happened

From 2026-06-18 to 2026-07-02 zero validation entries fired. Every scheduled
`ic-simple` run completed "success" while logging:

```
Gate state: mode=quarantine | scale_allowed=False | block_new_positions=True
Gate blocker: MATHEMATICAL QUARANTINE: ... New entries are blocked until
data/runtime/strategy_validation_hypothesis.json defines a changed-rule hypothesis ...
```

## Root cause

`north_star_guard._hypothesis_covers_rehabilitation_plan` requires the
hypothesis to cover the rehab plan's **top-3 loss clusters**. The 2026-06-18
`edge_rehabilitation_plan.json` promoted `long_hold_ge_7d` into the top 3;
the committed hypothesis covered only `ten_wide_wings, multi_contract,
early_exit_lt_24h`. Coverage check failed → permanent quarantine. A local
uncommitted edit fixed coverage but bundled an unauthorized 200%-stop change
and never landed.

Compounding defect: when entries did fire, `spy-core` still had
`wing_width=10.0` although the hypothesis prohibits 10-wide wings — cohort
entries weren't valid tests of the hypothesis.

## Fix (PR #4171, merged 2026-07-02, sha 428de0de1)

- Hypothesis covers `long_hold_ge_7d` + `early_exit_lt_1h`; explicit 7-DTE
  managed-exit rule. Exits unchanged (50% TP / 100% stop — canonical).
- `spy-core` wing_width 10 → 5.
- 200%-stop / 25%-TP redesign preserved at
  `data/runtime/proposals/validation_hypothesis_200pct_stop.json`
  as PENDING_CEO_APPROVAL.

## Prevention

`tests/test_validation_hypothesis_compliance.py` mirrors the guard gate in CI:
a rehab-plan update that invalidates the hypothesis, or profile drift from the
hypothesis (wing width, sizing, cadence, exits), fails CI loudly instead of
silently halting entries.

## Lesson

- "Workflow green" ≠ "system trading". Any gate that can block 100% of
  entries must fail loudly (CI or alert), not just log.
- When trade cadence stalls, grep the latest ic-simple log for
  `Gate blocker` before touching strategy parameters.
