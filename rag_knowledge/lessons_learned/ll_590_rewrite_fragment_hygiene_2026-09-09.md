# LL-590 Leftover rewrite fragments are not live modules (2026-09-09)

**ID:** LL-590
**Date:** 2026-09-09
**Status:** ACTIVE
**Related:** AGENT-598; prior cleanup LL-349, LL-187, LL-225.

## Lesson

`src/strategies/core_strategy.py_REWRITE_EXECUTE` was a 90-line leftover
`execute()` fragment (no imports, no callers). Live execution lives in
`src/strategies/core_strategy.py`. A whole-repo "delete unused Python"
pass would have also proposed 87 import-scan false positives and safety
CLIs such as `close_*`. Those are not delete candidates.

`scripts/detect_dead_code.py --ci` flagged `src/intel` as empty because
the walker ignored subpackages (`explainx/`). Empty-dir means leaf
directory, not namespace package.

## Prevention

- `scripts/audit_repository_hygiene.py` errors on leftover suffixes
  (`.py_REWRITE*`, `.py.bak`, `.py.orig`, `.py.tmp`, `.py_BAK`).
- `tests/test_repo_hygiene.py` asserts zero tracked leftovers.
- `find_empty_directories` skips directories that have subpackages.
- Prove zero callers (`rg`) before deleting a file that "looks unused".

## Do not

- Mass-delete files listed as "never imported" by the unused-file scan.
- Mass-delete `scripts/close_*` or other kill-switch/safety CLIs.
- Set `fail_under = 100` or compare coverage across different source scopes
  (LL-349).
- Line-by-line rewrite 214k Python lines as a hygiene session.
- Delete RAG lessons without a duplicate-ID or contradiction proof.
