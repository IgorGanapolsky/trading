# LL-643 — VS coverage FORMAT: baseline, then same-scope remeasure

Source: [Today I will improve test coverage](https://devblogs.microsoft.com/visualstudio/today-i-will-improve-test-coverage/) (Aaron Powell, 2026-09-15)

## Steal (FORMAT)

1. **Baseline first.** Do not write tests for the sake of writing tests.
2. **Target real gaps.** Skip files with nothing to test (enums / constants).
3. **Re-measure the same scope.** A new global percentage is not proof.

## Do not

- Clone Visual Studio Test Agent or Copilot `@test #solution`.
- Claim repo-wide 100% coverage (LL-640). Their 37% to 81% is _their_ Interview Coach sample.
- Add `cov-fail-under = 100` to pyproject.

## Ship

`scripts/coverage_gap.py` baseline|compare. Complements `scripts/ci/check_critical_coverage.py` (critical-file floors), does not replace it.

## Cash

Ops/eval only. Commercial fee-yes remains separate.
