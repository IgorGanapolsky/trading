# CI Runbook

## Workflow Tiers

- Tier 1 (blocking): `CI`, `CodeQL`, `Secrets Scan`, `Validate Documentation`
- Tier 2 (trading operations): `sync-alpaca-status.yml`, `daily-trading.yml`, `update-progress-dashboard.yml`
- Tier 3 (publishing/aux): pages/deploy and blog/report workflows

## Required Secrets

- `ALPACA_PAPER_TRADING_API_KEY`
- `ALPACA_PAPER_TRADING_API_SECRET`
- `ANTHROPIC_API_KEY` (where LLM actions are enabled)
- `OPENROUTER_API_KEY` (fallback routes)

## Failure Policy

- Tier 1: fail-closed (must pass before merge)
- Tier 2: fail-closed for trade execution, fail-open only for non-trading artifact publication
- Tier 3: fail-open allowed with alert/log evidence

## Incident Recovery

1. Identify failing run: `gh run list --repo IgorGanapolsky/trading --branch main --limit 20`
2. Inspect job logs: `gh run view <RUN_ID> --repo IgorGanapolsky/trading --log`
3. Classify:
   - secret/env mismatch
   - dependency/install failure
   - flaky external API
   - code regression
4. Apply fix on branch, run local targeted tests, then push.
5. Re-run failed workflow and confirm green status before merge.

## Fast Checks

- Workflow file syntax/contracts:
  - `python3 -m pytest tests/test_workflow_contracts.py -q`
- Local CI smoke:
  - `ruff check src/ scripts/`
  - `python3 -m pytest tests/unit -q`
