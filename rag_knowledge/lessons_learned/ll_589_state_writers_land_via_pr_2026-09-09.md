# LL-589 Scheduled state writers cannot push protected main (2026-09-09)

**ID:** LL-589
**Date:** 2026-09-09
**Status:** ACTIVE
**Related:** AGENT-597; arXiv ingest run 34319463737.

## Lesson

`main` is ruleset-protected: changes must go through a pull request and five
required checks. Scheduled Actions that `git commit` then `git push origin main`
(or `HEAD:main`) fail with GH013 even when `GH_PAT` is present, because the PAT
is not on the bypass list.

Evidence: Continuous ArXiv Research Ingest committed seven papers on the runner
then the push was declined. The same class is red on put-credit-validation,
sync-alpaca-status, and pre-market-sync.

## Prevention

- Land via `scripts/land_github_actions_pr.sh` onto `chore/auto-<slug>-<run_id>`.
- PR title must contain `[auto]`. Coordination skips `chore/auto-*` + `[auto]`.
- Job permissions: `contents: write` and `pull-requests: write` (not top-level).
- Contract: `tests/test_workflow_contracts.py` forbids `git push origin main`
  and `git push origin HEAD:main` in every workflow YAML.

## Do not

- Re-add `git push origin main` / `HEAD:main` to "fix" a stale ledger.
- Treat a GITHUB_TOKEN-only branch push as merge-ready if required checks never
  queue; keep checkout `token: ${{ secrets.GH_PAT || github.token }}` so the PR
  can trigger CI.
- Open GitHub Issues for a failed ingest (LL-569).
- Commit primary-checkout Gemini theater onto this issue (LL-588).
- Treat Run All Tests exit 124 at ~98% as a pin defect. It is the 28m core
  watchdog (LL-572 class). Core timeout is 36m; job timeout is 55m.
