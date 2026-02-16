# Profit Readiness Scorecard

## Gate Health
- lint_exit: 0
- test_exit: 0

## Metrics
- Win Rate: 100.00% [PASS] (sample_size=1)
- Max Drawdown (sync history): 0.03% [PASS] (equity_points=24)
- Execution Quality (valid trade records): 97.89% [PASS] (valid=93/95)
- Gateway Latency: 897 ms [PASS] (from artifacts/tars/smoke_metrics.txt)
- Gateway Cost (smoke call): $0.000045 [PASS] (set TARS_INPUT_COST_PER_1M and TARS_OUTPUT_COST_PER_1M for estimate)
- Weekly Qualified Setups: 0/3 [WARN] (north_star_weekly_gate.cadence_kpi)
- Weekly Closed Trades: 1/1 [PASS] (north_star_weekly_gate.cadence_kpi)

## 7-Day Delta
- Equity delta (2d): $-14.00 (-0.01%) [WARN]
- Monthly run-rate estimate: $-210.00/month [WARN]
- Data source: sync_health.history
- North Star target: $6,000/month after tax

## Interpretation
- PASS means metric is within current readiness threshold.
- WARN means metric needs improvement before scaling risk.
- UNKNOWN means data is not yet captured for this metric.

## Weekly Cadence & No-Trade Diagnostic
- Cadence Summary: Cadence KPI miss: one or more weekly minimums not met.
- Blocked Gate Categories: none
- Diagnostic Summary: Closed trades exist in lookback window; no-trade root cause not currently active.

