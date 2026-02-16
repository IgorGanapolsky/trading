# LL-353: PR Merge Requires CI-Lint + Content-Lint Alignment

**ID**: LL-353
**Date**: 2026-02-16
**Severity**: PROCESS
**Category**: Development Operations
**Status**: DOCUMENTED

## Context

PR #3452 initially failed `Lint & Format` even after Ruff fixes because the CI lint job also runs `scripts/lint_blog_posts.py --changed --strict`.

## What Failed

- `Lint & Format` failed on warnings in `docs/_reports/google-doc-sync-setup.md` due missing front matter metadata.
- Ruff-only local validation did not capture this failure mode.

## Corrective Action

1. Run all lint stages that CI executes (Ruff + blog lint) before merge.
2. Add missing front matter fields (`description`, `summary`, `hero_image`) for changed report/docs files.
3. Re-push branch and re-check check-runs for the exact head SHA.

## Evidence Pattern

- Verify failing check via Actions job URL in check-runs API.
- Pull job logs for root-cause extraction.
- Confirm check rerun success prior to merge.

## Tags

pr-management, ci-lint, blog-lint, branch-hygiene
