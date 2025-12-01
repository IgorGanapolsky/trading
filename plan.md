# Plan Mode Session: Agentic Day-Trading Support System
> Managed exclusively in Claude Code Plan Mode. Research only before approval.

## Metadata
- Task: Build coaching/reading/newsletter nodes + coordinator for day-trading enablement
- Owner: GPT-5.1 Codex (CTO)
- Status: APPROVED
- Approved at: 2025-12-01T21:20:00Z
- Valid for (minutes): 180

## Clarifying Questions
| # | Question | Resolution | Status |
|---|----------|------------|--------|
| 1 | Do these resources need to influence live trading logic? | Not yet; they produce prep artifacts that other orchestrators can consume via JSON/vector stores without mutating trading funnels. | Resolved |
| 2 | Where should raw definitions live so agents can self-update? | A new `config/day_trading_resources.yaml` describing coaching programs, book metadata, and newsletter feeds plus capture inbox targets. | Resolved |
| 3 | How do we represent insights for retrieval? | Store structured snapshots in `data/day_trading_resources/resource_state.json` and push text summaries into the existing `rag_store` so LangChain/MCP agents can query them. | Resolved |

## Execution Plan
1. Audit existing sentiment/RAG utilities plus newsletter analyzers to understand reuse points for the new knowledge base and ingestion outputs.
2. Introduce `config/day_trading_resources.yaml` and new `src/day_trading_support/models.py` + `config_loader.py` dataclasses to normalize coaching/book/newsletter definitions.
3. Implement ingestion nodes (`mentor_monitor.py`, `reading_ingestor.py`, `newsletter_harvester.py`) that fetch schedules/feeds, summarize content, and emit normalized payloads with timestamps and confidence flags.
4. Build a `ResourceVault` service that writes aggregated state to `data/day_trading_resources/resource_state.json`, indexes text into the Chroma vector store via `rag_store`, and exposes query helpers.
5. Create agent wrappers (`MentorMonitorAgent`, `StudyGuideAgent`, `MarketPrepAgent`) plus a top-level `DayTradeSupportOrchestrator` that coordinates nodes, produces daily action plans, and logs outcomes.
6. Ship an orchestration script (`scripts/day_trading_support_cycle.py`) and wiring so orchestrator outputs feed existing telemetry (e.g., writing markdown + JSON reports) without touching trading loops.
7. Add targeted pytest coverage for config loading, ingestion normalization, vault persistence, and orchestrator planning logic, then refresh docs (`docs/day_trading_support.md`, README) and progress log.

## Approval
- [x] Requirements captured and mapped to concrete modules/files
- [x] Clarifications resolved with storage + integration strategy
- [x] CTO Approval — GPT-5.1 Codex @ 2025-12-01T21:20:00Z

## Exit Checklist
- [x] Tests/lints for new modules executed
- [x] Docs & progress log updated
- [x] Resource orchestrator outputs committed and linked in README
