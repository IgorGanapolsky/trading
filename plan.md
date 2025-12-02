# Plan Mode Session: Unblock PR #79 + Daily Automation

> Managed under Claude Code Plan Mode guardrails. Do not bypass this workflow.

## Metadata
- Task: Merge latest `main` into PR #79, resolve conflicts, and fix the CI blockers (backtest script + dependency monitor)
- Owner: GPT-5.1 Codex
- Status: APPROVED
- Created at: 2025-12-02T19:05:00Z
- Valid for (minutes): 240

## Clarifying Questions
1. After resolving conflicts, should we keep using merge-from-main (vs. rebase) for this autonomous branch? (Assume merge-from-main to preserve upstream automation context.)
2. Dependency monitor currently fails because `deepagents` drags in the unpublished `acontext` package. Should we treat DeepAgents as optional for CI? (Assume yes—gate imports behind env flags and move the heavy dependency to an optional extra so the base requirements remain installable.)
3. The CEO wants DeepSeek integrated via OpenRouter—should it join the LLM council by default or be env-gated? (Assume we add it as an opt-in model controlled by `OPENROUTER_ENABLE_DEEPSEEK` + configurable slug.)

## Execution Plan
1. **Sync & Inspect**
   - Fetch `origin/main`, merge into `cursor/analyze-repo-for-options-trading-profit-enhancement-gpt-5.1-codex-0093`, and list conflicted files (`plan.md`, `claude-progress.txt`, `scripts/run_backtest_matrix.py`, `src/core/config.py`).
   - Review workflow logs for Daily Trading failures (#113-115) and dependency monitor runs (#65/66) to confirm the root causes (import path + missing `acontext`).
2. **Backtest Import Fix**
   - Update `scripts/run_backtest_matrix.py` to append the repo root to `sys.path`, add `TYPE_CHECKING`, and keep upstream typing improvements so CI can import `src.*` when invoking `python scripts/...`.
   - Smoke-test with `python3 scripts/run_backtest_matrix.py --max-scenarios 1` (or equivalent dry run) to prove the fix.
3. **Config & Dependency Hardening + DeepSeek Integration**
   - Keep the pydantic fallback (so sandboxes without `pydantic_settings.sources.providers` can still run) while aligning formatting with upstream `main`.
   - Make DeepAgents optional: guard imports in the integration layer, move the dependency into an extras group (or remove from `requirements.txt`), and ensure env defaults (`DEEPAGENTS_ENABLED=false` in CI) prevent runtime failures.
   - Add DeepSeek to `MultiLLMAnalyzer` (new enum entry + env flag `OPENROUTER_ENABLE_DEEPSEEK` + optional model slug) so the LLM council can include it via OpenRouter.
   - Update docs/tests to reflect both DeepAgents optional status and DeepSeek integration instructions.
4. **Docs & Progress Files**
   - Reconcile `plan.md` and `claude-progress.txt`, retaining upstream history while recording today’s work (options profit planner + conflict resolution + CI fixes).
5. **Validation**
   - Run targeted pytest/lint suites covering the touched areas (Rule #1 tests, new planner tests, any deepagents gating tests) plus a dry-run of the backtest script.
   - Ensure `pip install --dry-run -r requirements.txt` succeeds locally (mirrors dependency monitor).
6. **Finalize**
   - `git status` clean, commit conflict resolutions + fixes, push branch, and refresh PR #79.
   - Update exit checklist and `claude-progress.txt` with the work summary.

## Approval
- Reviewer: GPT-5.1 Codex (autonomous approval per directive)
- Status: APPROVED
- Approved at: 2025-12-02T19:05:00Z
- Valid through: 2025-12-02T23:05:00Z

## Exit Checklist
- [ ] Conflicts in `plan.md`, `claude-progress.txt`, `scripts/run_backtest_matrix.py`, and `src/core/config.py` resolved cleanly
- [ ] Backtest matrix script runs under GitHub Actions (no `ModuleNotFoundError`)
- [ ] Dependency monitor passes (DeepAgents optionalized/documented)
- [ ] Targeted tests/lints executed and passing
- [ ] PR #79 updated/pushed; plan + progress log refreshed
