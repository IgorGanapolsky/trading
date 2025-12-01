## Success Definition & Evaluation (Anthropic Playbook)

We now follow Anthropic’s **“Define Success”** guidance for test-and-evaluate workflows (see <https://platform.claude.com/docs/en/test-and-evaluate/define-success>). This document translates that framework into concrete, automated metrics for the trading stack so every feature, test run, and deployment is judged against the same success ladder.

### 1. Clarify Desired Outcomes

- **Business / North Star**: Hit $100/day by Month 6 via Fibonacci-compounded daily allocations without adding external capital.
- **System Reliability**: Sustain ≥99.9% successful trading runs (scripts + GitHub Actions) with no missed market windows.
- **Trader Safety**: Guardrail freshness checks for Finnhub macro signals and Sentry alerts must stay <15 minutes old during market hours.
- **User Experience / Insight**: Daily CEO reports, dashboard snapshots, and audit trails must explain why trades fired (momentum, RL, sentiment rationales).

### 2. Choose Observable Metrics

| Success Layer | Metric | Target / Guardrail | Source of Truth | Cadence |
| --- | --- | --- | --- | --- |
| Business | Rolling 30-day win rate | >60% | `data/system_state.json`, Alpaca API | Daily + weekly |
| Business | Sharpe ratio | >1.5 | Backtests + nightly reports | Weekly |
| Reliability | Successful orchestrator runs | ≥99.9% | GitHub Actions, `data/audit_trail/` | Daily |
| Reliability | Guardrail cache age | <15 min | `src/utils/economic_guardrails.py` telemetry | Intraday |
| Safety | Max drawdown | <10% | Reports + Alpaca | Daily |
| UX/Insight | Daily report completeness | 100% required fields | `reports/daily_report_YYYY-MM-DD.txt` | Daily |
| UX/Insight | Dashboard trend snapshot freshness | <24h | Streamlit dashboard logs | Daily |
| Testing | End-to-end funnel tests | 100% green (`tests/test_trading_e2e.py`) | Pytest CI | Per change |
| Testing | Sentry integration tests | 100% green (`tests/test_sentry_integration.py`) | Pytest CI | Per change |

### 3. Instrument Before You Experiment

- **Telemetry Hooks**: All orchestrator scripts must emit success metrics to `data/audit_trail/hybrid_funnel_runs.jsonl` so downstream evaluations can filter by trade gate.
- **Reports as Contracts**: The daily CEO report template now doubles as the UX acceptance checklist. Any missing field is a failure.
- **Guardrail Monitor**: Economic guardrail cache ages are logged and surfaced via dashboard badges; stale data blocks Tier 1/2 allocations automatically.
- **Dashboard Exposure**: Trend snapshots and guardrail status are streamed to the dashboard (per next steps in `claude-progress.txt`) so manual spot checks become self-serve.

### 4. Evaluate & Iterate

- **Daily**: Verify win rate, guardrail freshness, and report completeness before market close; log status diffs in `claude-progress.txt`.
- **Weekly**: Compare 7-day Sharpe and drawdown vs. targets; if out of bounds, open a remediation task and hold merges that don’t restore the metric.
- **Per Feature**: Every PR must state which success metric it influences and how it will be validated (tests + telemetry). Failing to update success evidence blocks merges.
- **Quarterly Checkpoint**: Map current metrics to the Day-90 go/no-go criteria in `docs/r-and-d-phase.md`; extend R&D if any Anthropic success guardrail is red.

### Implementation Workflow

1. **Define**: Before coding, declare which row(s) in the scorecard the change affects and what movement indicates success.
2. **Instrument**: Add logging/tests so the metric is automatically captured (no manual inspection).
3. **Run & Review**: Execute the relevant CI + trading jobs; compare outputs to the targets above.
4. **Document**: Update `claude-progress.txt`, dashboards, or reports with the observed metric deltas so future agents inherit the context.

By grounding each iteration in this success definition, we ensure experiments compound intelligently, regressions surface immediately, and the CEO always sees evidence tied directly to Anthropic’s evaluation framework.
