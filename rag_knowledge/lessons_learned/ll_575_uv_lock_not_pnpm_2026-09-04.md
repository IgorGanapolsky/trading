# LL-575: pnpm 12 FORMAT is lockfile honesty, not a Rust rewrite of uv

**Date:** 2026-09-04
**Severity:** 3
**Category:** dependencies, CI, honesty

## What happened

InfoQ reported pnpm 12 as a Rust rewrite that kept pnpm 11 commands and lockfile format. Theater in the primary checkout (`scripts/fast_python_dep_manager.py` and friends) treated that as "implement pnpm caching in Python" and cited 15ms / 90% as ours.

## Lesson

Keep `uv.lock`. Fail closed on a second package manager. Do not migrate this Python repo to pnpm. Vendor speedup curves stay vendor-owned.

## Prevention

`scripts/package_manager_honesty.py` + `tests/test_package_manager_honesty.py`.
