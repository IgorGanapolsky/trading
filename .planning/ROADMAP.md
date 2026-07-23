---
milestone: "v2.0-put-credit-edge"
title: "Put Credit Edge Proof → Smart Ops"
status: "active"
created: "2026-07-23"
---

# v2.0 — Put Credit Edge Proof (Ralph + GSD)

**Honesty gate:** Never claim profitable until closed put-credit cohort hits kill criteria  
(`n≥30`, expectancy>0, PF>1, total realized PnL>0). Live stays blocked until then.

## Phase 1: Cohort Truth Loop (IN PROGRESS)

- Put-credit cohort scorecard (family-isolated metrics)
- Open inventory + manage-exits + residual IC ops on every tick
- Ralph continuous tick script writing audit artifacts

## Phase 2: Smart Entry Quality

- Keep delta-band scan + min credit $0.50
- Surface daily/concurrent limits in scorecard
- Optional: credit/delta quality gates from realized losses only after n≥10

## Phase 3: Exit Intelligence

- PCS min 24h / TP 25% / stop 200% / 7 DTE (unchanged until evidence)
- Residual IC profit_pct_of_max ops visibility
- Stop refinement only after closed-cohort evidence (not vibes)

## Phase 4: Edge Decision Gate

- At n=30: EDGE_CANDIDATE vs NO_EDGE_KILL
- Live scale plan only if EDGE_CANDIDATE
- No IC revival by default

## Phase 5: Learning Stack

- Family-isolated ML/RAG (no IC metrics poisoning put-credit)
- Trajectory feedback from closed PCS only
- North Star progress from expectancy, not equity vibes
