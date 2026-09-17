---
id: LL-651
title: TypeSafe System One claim gate for edge honesty
date: 2026-09-17
severity: 4
tags: [typesafe, system-one, confidence-routing, claim-gate, agent-651]
---

## LL-651 — TypeSafe Hook → trading claim gate

## Context

Operator signed into the
[TypeSafe Hook console](https://console.typesafe.ai/hook).
`/hook` is the welcome + pop-quiz gate before API keys. Jev is **not** a chat
model; it returns typed Noul/Choice/Score judgments with calibrated
probabilities.

## Mistake class prevented

Agents asserting "profitable / positive expectancy / proven edge" while
`paired_buffett_closes < 30` and `live_blocked=true`.

## Fix

- `scripts/typesafe_claim_gate.py` — confidence-gated allow/abstain/deny
- Offline heuristic for CI; online Jev when `TYPESAFE_API_KEY` present
- Live smoke (same session): false edge claim → `deny` (0.85), severity ≈ 2.0

## Prevention

- Skill: `skills/typesafe-system-one-not-clone`
- Tests: `tests/test_typesafe_claim_gate.py`
- Key stored Keychain `TYPESAFE_API_KEY` / hermes-fleet (never in git)

## Do not

- Install TypeSafe as a product SKU or replace deterministic risk gates
- Treat Jev chatably; questions must define answer shape
