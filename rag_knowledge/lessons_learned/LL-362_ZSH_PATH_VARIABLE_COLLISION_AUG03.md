# LL-362: Never Reuse zsh's `path` Parameter

**ID**: LL-362
**Date**: 2026-08-03
**Severity**: MEDIUM
**Category**: shell reliability, operator hygiene
**Status**: ACTIVE

## Incident Summary

A read-only credential-discovery probe used `path` as a loop variable in zsh. In zsh,
`path` is the tied array form of `PATH`, so the assignment replaced executable search
directories with candidate filenames. Later `rg`, `head`, and `security` commands in
the same invocation failed with exit 127 and produced no valid credential evidence.

## Prevention Rule

Use task-specific shell variables such as `candidate_file`, `worktree_dir`, or
`credential_label`. Never assign `path`, `PATH`, `home`, `HOME`, or `CODEX_HOME`.
When an executable-discovery command returns 127, discard downstream conclusions and
rerun the entire probe after restoring an unmodified environment.

## Verification Rule

Credential availability is proved only by the corrected command's result. The failed
probe is evidence of an operator error, not evidence that a credential exists or is
missing.
