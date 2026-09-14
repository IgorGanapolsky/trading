# SPEC — Trading cash + harness residual

<!-- BMAD FORMAT steal (SaM / bmad-method SPEC.md contract): Why, Capabilities,
     Constraints, Non-goals, Success signal. Not an npx bmad-method install. -->

**Version:** 1.0.0  
**Updated:** 2026-09-14  
**Planning depth:** Quick Flow for harness; full depth for fee-yes ship  
**Stolen format:** BMAD SPEC.md five-element contract

## Why

Paper lab must not invent commercial grades. Cash fee-yes (prepaid Miramar ≥$100
non-owner Stripe + clerk+BCPA) is the binding unlock for overall A+/10. Meanwhile
the agent harness must stay anti-babysitting, spec-driven, and evidence-backed so
CI/cash residuals keep moving without CEO prompts.

## Capabilities (with success conditions)

| ID  | Capability           | Success condition                                                     |
| --- | -------------------- | --------------------------------------------------------------------- |
| C1  | Dual-grade honesty   | `fleet-a-plus` overall stays F while `cash_fee_yes` unmet             |
| C2  | Ralph/GSD tick       | `ralph_gsd_tick.py` emits phase_loop + STATE/CONTEXT                  |
| C3  | Spec Kit converge    | `speckit_converge.py` status=converged with ship_lock on cash         |
| C4  | Superpowers verify   | `superpowers_verify_complete.py --harness` ok=true                    |
| C5  | Call-sheet cash rail | CALL_SHEET_VERIFIED + prepaid drafts; checkout HTTP 200; no auto-send |
| C6  | Active scope freeze  | `audit_active_scope.py --json` ok=true; IC entries killed             |

## Constraints

1. Paper only; `live_blocked=true`; Buffett put-credit profile only.
2. Cold email FREEZE → phone/dial sheet; never auto-send.
3. No OnCore clerk-image spend without explicit CEO spend auth.
4. One Linear issue + one worktree; no lock steal.
5. Required CI green before merge; no force-push to main.
6. Credentials via env/keychain only.

## Non-goals

- Installing `bmad-method`, Spec Kit CLI, open-gsd npm, or Superpowers plugin into this lab.
- Claiming commercial DS/ML/Graph A+ or overall A+ before fee-yes.
- Reviving iron-condor / 0DTE entries.
- Building dashboards, publishing surfaces, or SaaS theater as “make money.”
- Auto-dialing or auto-sending buyer outreach.

## Success signal

**Harness Converged:** constitution + converge + verify-complete + active_scope all pass  
**AND** ship_lock remains documented until Stripe fee-yes + `clerk_image_ok`.

Overall letter may only rise when Success signal’s cash half clears — never from
harness green alone.
