# Judge Demo Checklist

## Must-Have Evidence
- [x] Gateway environment captured
- [x] Smoke response recorded
- [x] Smoke response includes completion choices
- [x] Trade opinion smoke recorded
- [x] Trade opinion smoke is actionable
- [x] Execution quality daily aggregate recorded
- [x] Resilience report recorded
- [x] Resilience report observed error-path signal
- [x] Retrieval report recorded
- [x] Submission summary generated
- [x] Latency/cost metrics captured

## Claim -> Evidence Mapping
- Routed model call works -> `artifacts/tars/smoke_response.json`
- Routed trade opinion is actionable -> `artifacts/tars/trade_opinion_smoke.json`
- Execution quality trend is tracked -> `artifacts/tars/execution_quality_daily.json`
- Failure path is handled -> `artifacts/tars/resilience_report.txt`
- Retrieval/memory readiness -> `artifacts/tars/retrieval_report.txt`
- Config + run summary -> `artifacts/tars/env_status.txt`, `artifacts/tars/submission_summary.md`

## Live Demo Sequence
1. Open `submission_summary.md` and state the claims.
2. Show `smoke_response.json` and point to completion choices.
3. Show `trade_opinion_smoke.json` and point to `actionable: true`.
4. Show `execution_quality_daily.json` and point to success/latency/cost rollup.
5. Show `resilience_report.txt` and explain fallback/error-path behavior.
6. Show `retrieval_report.txt` and describe memory/retrieval readiness.
7. Show `smoke_metrics.txt` for latency/token/cost context.

