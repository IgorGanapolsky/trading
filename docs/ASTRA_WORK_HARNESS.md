# OpenAI GPT-6 Astra Next-Generation Work & Agent Harness

## Source & Context

- **Announcement**: [GPT-6 Astra: The next generation in intelligence for work](https://openai.com/index/gpt-6-astra-next-generation-work/) (OpenAI, September 2026)
- **Paradigm**: The transition from conversational chat to a **Computer Operator / Work Operating System**.

---

## The Core Formula

$$\text{Agent} = \text{LLM} + \text{Context} + \text{Tools} + \text{Execution Loop}$$

1. **LLM**: Pluggable models (Local Apple Silicon MLX / Ollama, Qwen 3.8, OpenAI, Gemini).
2. **Context**: Task-adaptive JIT context compression (minimal token footprints, zero hallucinated noise).
3. **Tools**: Standardized, schema-validated tool interfaces with Model Context Protocol (MCP) compatibility.
4. **Execution Loop**: Stateful supervisor "Manager Loop" with mid-turn steering, invariant checkpoints, and cryptographic receipts.

---

## Key Transferable Capabilities

### 1. The Manager Loop (Supervisor + Subagent DAG)

The Manager Loop breaks down complex operational or trading goals into a directed acyclic graph (DAG) of typed sub-tasks:

- Tasks are ordered topologically.
- Each task specifies its assigned role, bounded tool access, prerequisite steps, and explicit Acceptance Criteria (ACs).

### 2. Action Risk Tiering & Pre-Action Interdiction

Actions are strictly classified into 5 safety tiers:

- `READ_ONLY`: Status checks, logs, file viewing, git inspection (always allowed).
- `DRY_RUN_SAFE`: Simulations, dry-run orders, paper calculations.
- `STATE_MODIFYING`: Local file edits, worktree branching, test runs.
- `CONSEQUENTIAL_EXTERNAL`: Git push, PR merges, external network requests, Stripe checkout.
- `FORBIDDEN`: Live broker order submissions, force push to main, database deletions (blocked fail-closed).

### 3. Mid-Turn Steering & Invariant Guardrails

If an execution step encounters a warning, permission violation, or drift from safety constraints, the supervisor intervenes mid-turn to:

- Halt dangerous operations immediately.
- Re-route to safe alternative tools or isolate worktrees.
- Attach structured warnings to the audit receipt.

### 4. Verifiable Execution Receipts

Every supervisor loop run generates an immutable, SHA-256 fingerprinted audit receipt containing:

- Receipt ID (`ASTRA_<hash>`)
- Completed, steered, and failed step counts
- Sub-millisecond latency measurements
- Exact tool invocations and acceptance verification states

---

## CLI & Makefile Usage

```bash
# Run Astra Work Harness Doctor
uv run scripts/astra_work_harness.py --doctor

# Plan a goal into an Astra Supervisor DAG
uv run scripts/astra_work_harness.py --plan "daily spy put credit cycle"

# Execute Manager Loop with mid-turn checkpoints
uv run scripts/astra_work_harness.py --run-loop "daily trading cycle"

# Classify tool risk
uv run scripts/astra_work_harness.py --classify "submit_order"

# Makefile Target
make astra-roi
```
