# Temporal durability for OpenAI Agents SDK (Dec 7, 2025)

## Why Temporal?

- The July 30, 2025 Temporal announcement confirms the OpenAI Agents SDK + Temporal integration is in Public Preview, so we can layer each `Runner` invocation on Temporal Workflows for durable, restartable execution and automatic retries when LLM or API calls fail. citeturn0search2
- The Temporal changelog notes the handoff transcript now begins with “For context, here is the conversation so far between the user and the previous agent,” so our supervisor should keep the same labeled summaries we already introduced in `src/openai_agents/runtime.py` to stay compatible with that default. citeturn0search6

## Proposed integration path in this repo

1. Wrap `run_supervisor_sync` inside a Temporal Workflow (Python SDK) that acts as an `Activity` or `Workflow` entry point. The Workflow can record the `prompt`, run the supervisor, and persist the `final_summary` so we can resume long-running planning or gate approvals without losing progress. citeturn0search0
2. Use Temporal Task Queues for each agent stage (research, risk, execution) if we need finer-grained retries or parallelism, letting Temporal enforce `nextRetryDelay`/`collision policy` while we keep the SDK instructions lean. citeturn0search0
3. Provide a local `scripts/run_agents_temporal_workflow.py` (or similar) that mirrors `scripts/run_agents_sdk_example.py` but kicks off the Temporal Workflow, offering a durable runner for production-level jobs.

## Next autonomous steps

- Prototype a Temporal Workflow module that calls `Runner.run_sync` and surfaces the `final_summary`/`trace_id` as Workflow outputs.
- Document the Temporal workflow (including required environment variables, task queues, and session path for SQLite) so other teams can adopt it without touching the core orchestrators.
- Set up a small smoke test that runs the Temporal Workflow in the local Temporal server (via `temporal cadence` or `temporal` CLI) to prove the durability path before moving it into nightly orchestrations.
