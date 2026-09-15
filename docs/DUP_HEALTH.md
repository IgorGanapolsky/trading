# Maintainability health (GitClear FORMAT)

<!-- FORMAT steal from GitClear Maintainability Gap + Diff Delta / hotspot /
     tripwire surfaces. Not a GitClear SaaS, Databricks, or attribution product. -->

**Sources:**

- [GitClear](https://www.gitclear.com/)
- [The Maintainability Gap](https://www.gitclear.com/the_ai_code_quality_maintainability_gap)
- [TNS summary](https://thenewstack.io/ai-coding-duplication-rose/)

## Steal (what we run locally)

| GitClear signal   | Industry                 | Our rail                                        |
| ----------------- | ------------------------ | ----------------------------------------------- |
| Block duplication | +81% (40.3→73.0 / MLOC)  | `blocks_per_million`                            |
| Moved / refactor  | 21%→3.8%                 | `--git-range` `moved_ratio`                     |
| Error-masking     | +47%                     | `error_masking` (bare except / Exception: pass) |
| Two-week churn    | +15%                     | `--churn-days 14` retouch ratio                 |
| AI hotspot dirs   | defect/dup Δ by folder   | `hotspots.directories`                          |
| Diff Delta        | durable change ≠ raw LOC | `diff_delta_proxy`                              |
| Five tripwires    | concrete leader moves    | `tripwires[1..5]`                               |

## Commands

```bash
python3 scripts/dup_health.py --path scripts --path src
python3 scripts/dup_health.py --git-range HEAD~30..HEAD --churn-days 14 --strict
python3 scripts/ralph_gsd_tick.py --dup-health --path scripts --churn-days 14
```

## Five tripwires (local status)

1. Budget refactor + legacy touch
2. Duplicate-block tripwire
3. Review error-masking explicitly
4. Coach/gate thin-judgment hotspot directories
5. Measure structure (Diff Delta), not volume

## NEVER

- Install / buy GitClear SaaS for this paper lab
- Equate AI LOC / PR count with fee-yes or commercial A+
- Dual-edit agy AGENT-624 conformance engine

## Related

InfoQ SDD attribution (`docs/SPEC_GOVERNANCE.md`) catches intent drift; this catches
copy-paste sprawl, swallowed errors, and churn theater.
