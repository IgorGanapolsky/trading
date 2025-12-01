# Agentic Day-Trading Support System

_Last updated: 2025-12-01_

This document explains the new coaching/education/newsletter automation that feeds trader readiness artifacts into the broader multi-agent stack.

## Why it exists

The CEO mandated that coaching, study, and market-prep inputs be automated just like trade execution. Manual prep is error-prone and does not scale. The support orchestrator delivers:

- **Mentor coverage**: surfacing Bear Bull Traders + Warrior Trading touchpoints with timestamps and accountability prompts.
- **Study plans**: allocating book chapters and lessons from Turner, Logue, and Aziz to the day’s focus tags.
- **Newsletter digestion**: harvesting Barchart/Bloomberg feeds, extracting tickers, and logging actionable summaries.
- **Persistence**: JSON + Markdown artifacts plus vector embeddings so any agent (LangChain, MCP, DeepAgents) can ground planning conversations in the same prep data.

## Architecture

```
config/day_trading_resources.yaml (source of truth)
                │
                ▼
MentorMonitorAgent ──► Coaching sessions (CoachingProgram ➜ CoachSession)
StudyGuideAgent  ──► Reading assignments (BookResource ➜ ReadingAssignment)
MarketPrepAgent  ──► Newsletter insights (NewsletterResource ➜ NewsletterInsight)
                │
                ▼
DayTradeSupportOrchestrator ──► DailySupportPlan
                │
                ├── ResourceVault → data/day_trading_resources/*.json
                ├── Markdown report → reports/day_trading_support_YYYY-MM-DD.md
                └── ResourceVectorStore (Chroma collection: day_trading_resources)
```

### Key modules

| Module | Path | Responsibility |
| --- | --- | --- |
| Metadata config | `config/day_trading_resources.yaml` | Declarative definition of coaching programs, book summaries, newsletter feeds. |
| Data models | `src/day_trading_support/models.py` | Dataclasses for templates, lessons, assignments, insights, final plan. |
| MentorMonitorAgent | `src/day_trading_support/mentor_monitor.py` | Computes the next actionable sessions per coaching program with timezone awareness. |
| StudyGuideAgent | `src/day_trading_support/reading_ingestor.py` | Allocates reading plan segments + lessons by focus tag and time budget. |
| MarketPrepAgent | `src/day_trading_support/newsletter_harvester.py` | Pulls RSS feeds (Barchart/Bloomberg), extracts tickers, rates urgency. |
| ResourceVault | `src/day_trading_support/resource_vault.py` | Writes JSON/Markdown snapshots and indexes text into Chroma via `ResourceVectorStore`. |
| Orchestrator | `src/day_trading_support/orchestrator.py` | Coordinates agents, assembles `DailySupportPlan`, and triggers persistence. |
| CLI | `scripts/day_trading_support_cycle.py` | Run the orchestrator locally or inside CI. |

## Usage

```bash
# Generate a full plan, print JSON, and write artifacts
PYTHONPATH=src python3 scripts/day_trading_support_cycle.py \
  --focus psychology --focus execution \
  --study-minutes 60 \
  --print-json
```

Outputs:

- `data/day_trading_resources/resource_state.json` (latest plan).
- `data/day_trading_resources/resource_state_YYYY-MM-DD.json` (date-stamped snapshot).
- `reports/day_trading_support_YYYY-MM-DD.md` (Markdown summary for CEO + dashboards).
- Chroma embeddings stored under `data/rag/vector_store/day_trading_resources` (if `chromadb` is installed). If `chromadb` is unavailable the system simply skips embeddings and logs a warning.

## Configuring resources

Edit `config/day_trading_resources.yaml` to adjust schedules, add lesson blocks, or onboard new newsletters. Schema tips:

- **Coaching programs**: add `session_templates` entries with `cadence` (`daily`, `weekdays`, `weekly`) and optional `day_of_week`.
- **Books**: supply `lessons` (actionable prompts) and `reading_plan` entries with time estimates.
- **Newsletters**: include `feed_url` (RSS) plus `window_hours` so stale issues are ignored. Multiple Bloomberg variants are supported simultaneously.

After editing, run the CLI (or call `DayTradeSupportOrchestrator.run`) to validate the YAML. Tests `tests/test_day_trading_support.py` cover parsing + orchestration.

## Integration points

- `ResourceVectorStore` uses the same Chroma root as the sentiment RAG so LangChain agents can query prep artifacts alongside Reddit/news data.
- The Markdown report can be surfaced on the Streamlit dashboard alongside trading telemetry (future work item).
- `DailySupportPlan.to_dict()` is JSON serializable; other agents can load `data/day_trading_resources/resource_state.json` to drive context windows or autop-runbooks.

## Extending

- Add more coaching programs by appending to `coaching_programs` in the YAML.
- Drop PDF/EPUBs for additional books into `data/day_trading_resources/source_material/` (optional) and update the YAML to reference new lessons.
- Expand newsletters by providing RSS endpoints (Seeking Alpha, The Fly). MarketPrepAgent will automatically parse ticker mentions.
- Integrate with MCP by having a Claude Agent read the Markdown + vector store and suggest prep tasks before `autonomous_trader.py` executes.

## Testing

```
python -m pytest tests/test_day_trading_support.py -q
```

The suite mocks RSS feeds, vector stores, and vault paths, so it runs quickly and deterministically.
