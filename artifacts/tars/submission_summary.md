# TARS Hackathon Automation Summary

Generated: 2026-02-24T19:07:26Z

## Artifacts
- env status: `artifacts/tars/env_status.txt`
- smoke response: `artifacts/tars/smoke_response.json`
- trade opinion smoke: `artifacts/tars/trade_opinion_smoke.json`
- smoke metrics: `artifacts/tars/smoke_metrics.txt`
- execution quality daily: `artifacts/tars/execution_quality_daily.json`
- resilience report: `artifacts/tars/resilience_report.txt`
- retrieval report: `artifacts/tars/retrieval_report.txt`

## Judge-ready claims (evidence-backed)
- Gateway route configured and validated via smoke call output
- Trade opinion route validated with actionable output gate
- Daily execution quality aggregation tracks latency/cost/success trends
- Error-path behavior validated via invalid-model resilience test
- Retrieval stack readiness validated via repo checks
