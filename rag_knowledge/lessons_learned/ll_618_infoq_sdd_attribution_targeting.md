# LL-618 — InfoQ SDD: attribution + targeting (not recall theater)

**Date:** 2026-09-15  
**Source:** <https://www.infoq.com/articles/when-spec-driven-development-pays-off/>  
**PR:** #4690 / AGENT-623 `85bccda37`

## Lesson

Specification baselines did not raise bug **recall** in the InfoQ study; they raised
**attribution** (findings cite named invariants). Easy-task “spec-first” gains were
mostly a **reasoning** effect. Full SDD ceremony pays on hard multi-constraint work.

## Prevention (this repo)

- `scripts/sdd_targeting.py` / `ralph_gsd_tick.py --sdd-target` → full|quick|skip
- `scripts/spec_drift_review.py` / `--spec-drift` → every finding cites `INV_*`
- `docs/SPEC_GOVERNANCE.md` — five control points + RACI (model Responsible, human Accountable)
- Do not dual-edit agy AGENT-624 conformance engine

## Evidence

`pytest tests/test_sdd_infoq_steal.py` — 13 passed (2026-09-15).
