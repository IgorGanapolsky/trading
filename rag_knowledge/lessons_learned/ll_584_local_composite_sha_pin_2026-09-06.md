# LL-584 Local composite `uses: ./` is SHA-pin legal (2026-09-06)

## Lesson

AGENT-583 landed `uses: ./.github/actions/setup-uv-python` in
`.github/workflows/agent-coordination.yml`. Scorecard Pinned-Dependencies
treats repo-local composites as pinned. `test_actions_are_sha_pinned`
already allowed `./` and `docker://`.

`test_github_workflow_is_bounded_and_sha_pinned` still required every
`uses:` to match `[^@]+@[0-9a-f]{40}`. Main CI `Run All Tests`
(run 34055301708 on `664839338980176ed52ec3d67606e0026d939106`) failed
that test first, then the 28m core phase exited 124. SonarCloud coverage
ran the same suite and failed the same way.

## Prevention

Keep the SHA-pin exception identical in both tests: skip `./` and
`docker://`, fail any other unpinned remote action. A unit fixture
asserts `./.github/actions/setup-uv-python` is not an offender while
`actions/setup-python@v5` still is.

## Do not

- Revert the local composite to an unhashed pip install to satisfy the
  stricter coordination test
- Enable `enforce_admins` to "fix" remaining Scorecard Branch-Protection
