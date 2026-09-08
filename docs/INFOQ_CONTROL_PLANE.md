# InfoQ Sep 8 2026 control plane (trading)

FORMAT steals from the InfoQ newsletter (Gisting, context engineering, Airbnb Flexible Auth, DoorDash Flux, AI review on low-risk PRs). **Not** product clones. **Not** Harness / Moderne / Foundry / billed Copilot Code Review spend.

| Theme                                     | Trading surface                                                      |
| ----------------------------------------- | -------------------------------------------------------------------- |
| Shopify Gisting / context engineering     | `src/ops/context_gist.py` + `scripts/context_gist.py`                |
| Airbnb Flexible Auth (policy challenges)  | `src/risk/entry_challenge_matrix.py` + `scripts/entry_challenges.py` |
| DoorDash Flux task graph                  | `src/ops/flux_task_graph.py` + `scripts/flux_graph.py`               |
| Skip peer review on low-risk / AI approve | `src/ops/pr_risk_classifier.py`                                      |
| pnpm 12 lockfile honesty (already landed) | `src/ops/package_manager_honesty.py`                                 |
| Doctor CLI                                | `scripts/infoq_agent_control_plane.py`                               |

## Commands

```bash
# Full doctor (exit 0 only when all dimensions ok)
.venv/bin/python scripts/infoq_agent_control_plane.py \
  --acs 'tests pass|CLI fail-closed' \
  --paths 'src/ops/context_gist.py,tests/test_context_gist.py,docs/INFOQ_CONTROL_PLANE.md'

# Gist a session pack
.venv/bin/python scripts/context_gist.py \
  --goal 'put credit dry-run' --in-scope 'paper plan' --out-scope 'live submit' \
  --ac 'tests pass' --ac 'CLI exit 0' --compact

# Entry challenges (exit 2 when blocked)
.venv/bin/python scripts/entry_challenges.py --iv-rank-proxy 12.3

# Operator flux graph
.venv/bin/python scripts/flux_graph.py --graph dry_run_readiness

make infoq-roi
```

## Explicit non-goals

- Do not attend / buy the Harness webinar as the deliverable.
- Do not enable billed Copilot Code Review.
- Do not migrate to pnpm; `uv.lock` stays canonical.
- Do not clone DoorDash Flux cloud agents or Airbnb auth product.
- Do not claim Continuity / Tether for trading.
