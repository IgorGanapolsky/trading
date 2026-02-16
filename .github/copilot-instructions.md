# Copilot Instructions for `trading`

Follow these rules for all code changes in this repository.

## Core Workflow (Layered TDD)

0. Bootstrap local loop toolchain once per environment:
   - `./scripts/layered_tdd_loop.sh bootstrap`
1. Start with a backlog pass:
   - `./scripts/layered_tdd_loop.sh analyze`
   - Use `artifacts/devloop/tasks.md` as the canonical task board.
2. Pick one Layer 1 item only (smallest possible fix).
3. Implement minimal code changes.
4. Re-run checks:
   - `./scripts/layered_tdd_loop.sh analyze`
5. Repeat until Layer 1 is empty.

## Task List Discipline

- Keep work tracked in file-based task lists only (no ephemeral plans).
- Treat `artifacts/devloop/tasks.md` checkboxes as source of truth.
- Work only unchecked Layer 1 items (`- [ ] ...`) first.
- After each analyze run, ensure resolved items are checked in `Completed Since Last Iteration`.
- Do not start Layer 2/3 work until Layer 1 is fully checked.

If checks are already green, propose the next highest-impact improvement from `artifacts/devloop/tasks.md`.

## Change Scope

- Prefer small, surgical diffs.
- Do not refactor unrelated files.
- Keep behavior stable unless tests explicitly require a change.
- Add/adjust tests whenever logic changes.

## Quality Gates

Before finishing, run at minimum:

- Profit profile loop: `./scripts/layered_tdd_loop.sh run`
- Full profile (periodic): `PROFILE=full ./scripts/layered_tdd_loop.sh analyze`

If tools are missing, use local venv (`.venv-devloop`) and document exactly what was run.

## Tetrate / Gateway Conventions

- Use OpenAI-compatible gateway config helpers in `src/utils/llm_gateway.py`.
- Gateway env vars:
  - `LLM_GATEWAY_BASE_URL`
  - `LLM_GATEWAY_API_KEY` (or `TETRATE_API_KEY`)
- Never hardcode provider keys or base URLs in source.

## Secrets and Safety

- Never commit secrets or tokens.
- Never print full secret values in logs or output.
- Use masked status only (set/unset or redacted).

## Project Context

- This is a trading system; prioritize correctness and risk controls.
- Preserve guardrails in risk/execution paths.
- Prefer explicit failure handling over silent fallback.
