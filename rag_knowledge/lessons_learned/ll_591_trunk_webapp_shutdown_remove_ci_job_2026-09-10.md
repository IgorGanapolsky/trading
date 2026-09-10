# LL-591: Trunk web app shut down — remove CI Trunk Check job

**Date**: 2026-09-10
**Severity**: 3 (MEDIUM — recurring false red on every PR)
**Category**: CI hygiene / dead third-party job

## What Happened

PR #4546 (arxiv ingest auto) showed `Trunk Check` FAILURE while required checks were green or in progress. Annotations:

- `Input 'trunk-token' has been deprecated ... The Trunk web app has been shut down; uploads are no longer supported.`
- Process exit code 1

Required branch protection contexts do **not** include Trunk Check (`Detect Changed Paths`, `Run All Tests`, `Validate Workflows`, `CodeQL`, `Dependency Review`).

## Lesson

1. Do not treat Trunk Check red as a merge blocker on this repo.
2. Remove dead vendor jobs when the product is shut down — leave them and every PR looks "failed" in the UI.
3. Lock removal with `tests/test_ci_runner_wiring.py` asserting `trunk-io/trunk-action` stays absent.
4. `dependabot-trunk-automerge.yml` is Dependabot auto-merge naming, not the Trunk.io product — do not delete it when removing `trunk-check`.

## Evidence

- AGENT-600 / PR #4547
- Annotation on run 34445613010 job Trunk Check
