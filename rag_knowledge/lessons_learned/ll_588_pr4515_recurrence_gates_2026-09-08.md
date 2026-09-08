# LL-588 — PR #4515 recurrence gates (absolute path / SSRF userinfo / Gemini pollution)

**ID:** LL-588  
**Date:** 2026-09-08  
**Status:** ACTIVE  
**Related:** AGENT-595 merged as #4515 (`529f90d7525847e82638f605186ee71d593a574b`); AGENT-596 prevention.

## What happened

CEO asked after merge: will these problems happen again? Three distinct failure classes blocked or polluted #4515:

1. **Absolute `/Users/<user>/` paths** in a RAG lesson → `audit_repository_hygiene.py` `absolute-user-path` error in CI.
2. **SSRF-shaped network allowlist** — `userinfo@host` authority tricks (`https://api.alpaca.markets:443@evil.example`) if hostname is not parsed via `urlsplit`.
3. **Rogue Gemini theater commits** onto a claimed worktree branch + leftover untracked Gemini WIP on the primary checkout.

## What is gated now (evidence)

| Class                            | Gate                                                                                                                                                              | Recurrence if gate stays                                                                                       |
| -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| Absolute user paths              | `scripts/audit_repository_hygiene.py` + `make audit` / CI; regression in `tests/test_repository_hygiene_audit.py`; local `scripts/check_staged_absolute_paths.py` | Will **fail CI / local check** before merge                                                                    |
| Userinfo host spoof              | `src/ops/agent_environment_doctor.py` `_domain_allowed` uses `urlsplit`; `test_network_rejects_userinfo_host_spoof`                                               | This **doctor bug** will not silently return                                                                   |
| Gemini theater on claimed branch | Process: worktree + Linear/vault claim + refuse `git add -A` on primary                                                                                           | **Not mechanically impossible** — sibling agents can still commit onto a shared branch if isolation is skipped |

## What can still recur

- Agents writing `/Users/...` into lessons (caught, not prevented at write time).
- Primary-checkout untracked Gemini/edge/context theater SKUs being force-added (`git add -A`).
- Sibling agents pushing onto another agent's claimed branch when worktree/claim protocol is skipped.
- Vision/OCR misreads of screenshots (process; use OCR for text UIs).

## Prevention actions

1. Never paste real home paths into RAG/docs; use `/Users/.../`.
2. Run `make audit` / `python scripts/check_staged_absolute_paths.py` before push.
3. Network allowlists must use `urlsplit` hostname only; keep the userinfo spoof test.
4. Do not commit primary Gemini theater WIP onto unrelated issue branches; claim + dedicated worktree only.
5. Do not claim "won't happen again" without a gate — recovery without a gate is recurrence.

## Non-goals

- Deleting another agent's untracked Gemini WIP on primary without their claim release.
- Weakening hygiene exemptions for `tests/`.
