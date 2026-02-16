# Manual Layer 1 Tasks


- [x] Tetrate trade-opinion flow: added routed multi-model trade-opinion request + fallback verification artifact (`artifacts/tars/trade_opinion_smoke.json`) and actionable-output gate in `scripts/tars_autopilot.sh full`.
- [x] Tetrate execution quality loop: added per-run metrics rollup + daily aggregate artifacts (`artifacts/tars/execution_quality_events.jsonl`, `artifacts/tars/execution_quality_daily.json`, `artifacts/tars/execution_quality_daily.md`) via `scripts/generate_tars_execution_quality.py`.
- [x] Add gateway cost defaults support in TARS flow so scorecard no longer shows `Gateway Cost: UNKNOWN`.
- [x] RAG synthesis pipeline: auto-ingest new `artifacts/tars/*.json|*.txt` into `rag_knowledge/lessons_learned/` and reindex with validation artifact proving new chunks were added. (Done: `artifacts/devloop/tars_rag_ingest_report.md` + `artifacts/devloop/tars_rag_validation.md`, delta chunks `+12`, delta files `+6`.)
- [ ] Add expectancy metrics (profit factor, avg winner, avg loser) to `scripts/generate_profit_readiness_scorecard.py`.
- [ ] Add a promotion gate artifact that blocks strategy promotion when win rate/run-rate thresholds are below target.
