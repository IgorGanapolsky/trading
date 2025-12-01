# Plan Mode Session: Promotion Gate + Backtest Matrix + Telemetry
> Managed in Claude Code Plan Mode. Do not modify outside Plan Mode workflow.

## Metadata
- Task: Enforce R&D promotion gate, expand backtest coverage, and surface telemetry dashboards
- Owner: GPT-5.1 Codex
- Status: APPROVED
- Approved at: 2025-12-01T22:05:00Z
- Valid for (minutes): 180

## Clarifying Questions
| # | Question | Resolution | Status |
|---|----------|------------|--------|
| 1 | What metrics determine promotion to live trading? | Use existing R&D criteria (win rate >60%, Sharpe >1.5, max drawdown <10%, profitable 30 consecutive days, no critical bugs) by parsing audit/backtest JSON artifacts. | Resolved |
| 2 | Where will scenario backtest artifacts live? | Store standardized JSON + Markdown reports per scenario under `data/backtests/<strategy>/<scenario>/` to keep history and allow CI assertions. | Resolved |
| 3 | How should telemetry be consumed? | Build a lightweight Streamlit dashboard backed by existing JSONL audit trail plus an optional CLI report writer for headless runs; expose summary metrics + gate pass/fail counts. | Resolved |

## Execution Plan
1. Inventory existing audit/backtest outputs to confirm available metrics and add helpers to parse them.
2. Implement `scripts/enforce_promotion_gate.py` that aggregates recent metrics and exits non-zero if promotion criteria unmet; expose toggles for paper/live mode.
3. Wire promotion guard into CI (daily trading + relevant workflows) and add docs describing the automated gate and manual override procedure.
4. Create scenario definition YAML (e.g., bull, bear, high-vol) and implement `scripts/run_backtest_matrix.py` that iterates scenarios, runs backtests, and saves JSON/Markdown reports.
5. Add pytest coverage for the promotion guard + scenario runner plus snapshot-based verification of output schemas.
6. Build telemetry surface: parse `data/audit_trail/hybrid_funnel_runs.jsonl`, aggregate gate stats, and expose both a CLI summary (`scripts/generate_telemetry_report.py`) and an optional Streamlit app under `dashboard/`.
7. Update README/docs to reference the new guard, backtest matrix, and telemetry views; ensure CI/docs link to generated artifacts.

## Approval
- [x] Requirements captured with repo impact
- [x] Clarifications resolved with storage, metrics, and UX decisions
- [x] CTO Approval — GPT-5.1 Codex @ 2025-12-01T22:05:00Z

## Exit Checklist
- [x] Promotion gate script + CI guard added
- [x] Backtest matrix automation + tests committed
- [x] Telemetry dashboard/report added with docs updated
