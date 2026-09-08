# LL-586 — InfoQ Sep 8 FORMAT steals for trading control plane (2026-09-08)

## Context

CEO asked to implement/test high-ROI improvements from InfoQ PDF
(local Downloads copy of infoq.pdf; do not commit absolute machine paths).
PR #4514 / AGENT-593.
Merged as `218c15eaa69a24e0528eacf742bc597949b1c923`.

## Steal (FORMAT only — not SaaS clones)

| Theme                                     | Trading surface                                           |
| ----------------------------------------- | --------------------------------------------------------- |
| Shopify Gisting / context engineering     | `src/ops/context_gist.py`                                 |
| Airbnb Flexible Auth challenges           | `src/risk/entry_challenge_matrix.py`                      |
| DoorDash Flux task graph                  | `src/ops/flux_task_graph.py`                              |
| Skip peer review on low-risk / AI approve | `src/ops/pr_risk_classifier.py`                           |
| pnpm lockfile honesty (already landed)    | `src/ops/package_manager_honesty.py`                      |
| Doctor                                    | `scripts/infoq_agent_control_plane.py` + `make infoq-roi` |

## Non-goals

Harness webinar, Moderne, Foundry/Ori, billed Copilot Code Review,
DoorDash Flux cloud, Airbnb auth product, Tether, pnpm migrate.

## Prevention

- `make infoq-roi`; path-normalize PR classifier; fail-closed entry challenges;
  gist dropped diagnostics bounded in token budget.
