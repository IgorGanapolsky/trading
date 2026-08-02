---
milestone: "v2.0-put-credit-edge"
title: "Put Credit Edge Proof → Smart Ops"
status: "active"
created: "2026-07-23"
updated: "2026-07-24"
framework: "ralph+gsd"
---

# v2.0 — Put Credit Edge Proof (Ralph + GSD)

**Honesty gate:** Never claim profitable until closed put-credit cohort hits kill criteria  
(`n≥30`, expectancy>0, PF>1, total realized PnL>0). Live stays blocked until then.

## Phase 1: Cohort Truth Loop — DONE (2026-07-24)

- [x] Put-credit cohort scorecard (family-isolated metrics)
- [x] Open inventory + manage-exits + residual IC ops on every tick
- [x] Ralph continuous tick script writing audit artifacts
- [x] Structure daily max=3 for put-credit (#4278)
- [x] Fillability ranking + cancel unfilled resting limits

## Phase 2: Smart Entry Quality — IN PROGRESS

- [x] Delta-band scan + min credit $0.50
- [x] Daily/concurrent limits in scorecard / gate
- [x] Regime gate IVR≥30 / VIX≤30 + entry regime logging (#4280)
- [x] Exit counterfactuals 50% TP / 21 DTE vs our 25% / 7 DTE
- [x] Rolling 20-trade metrics on scorecard
- [ ] Ralph tick includes `--regime-status` (this PR)
- [ ] Hard RAG / no ML theater on fills (#4281)
- [ ] Optional: credit/delta quality gates from realized losses only after n≥10

## Phase 3: Exit Intelligence

- [x] PCS min 24h / TP 25% / stop 200% / 7 DTE (profile locked)
- [x] Residual IC profit_pct_of_max ops visibility
- [ ] Stop refinement only after closed-cohort evidence (not vibes)

## Phase 4: Edge Decision Gate

- [ ] At n=30: EDGE_CANDIDATE vs NO_EDGE_KILL
- [ ] Live scale plan only if EDGE_CANDIDATE
- [x] No IC revival by default (kill switch)

## Phase 5: Learning Stack

- [x] Family-isolated confidence priors (put-credit cold start)
- [ ] Hard RAG groundedness on openings (#4281)
- [ ] Trajectory feedback from closed PCS only
- [ ] North Star progress from expectancy, not equity vibes
