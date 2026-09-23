---
name: pstack-how
description: "Conduct read-only runtime tracing and subsystem mental model generation without modifying code. Use when exploring unfamiliar modules, understanding data flow through trading risk rails, mapping order execution pipelines, or preparing for refactoring."
---

# pstack: /how (Subsystem Investigation & Runtime Tracing)

The `/how` skill implements the investigation discipline from the **pstack** engineering playbook (by Lauren Tan / `@poteto`). It builds complete, high-fidelity mental models of subsystems and traces execution flows from user entrypoints to outputs **without making any code changes**.

---

## Operating Invariants

1. **Read-Only**: Strictly zero mutations to files or repository state during this phase.
2. **Caller-to-Persistence Tracing**: Trace flows starting from the caller entrypoint (CLI command, API route, cron job) all the way down to I/O, external broker APIs, or durable ledgers.
3. **Explicit Invariant Extraction**: Identify what assumptions the code makes about inputs, state transitions, and concurrency locks.
4. **Structured Artifacts**: Synthesize findings into sequence flows, state diagrams, and boundary catalogs.

---

## Tracing Procedure

### Step 1: Identify Entrypoint & Public Contract
Find the initial surface invoked by the operator or scheduler:
- In trading engine: `scripts/spy_put_credit.py` (active paper options workflow) or `scripts/system_health_check.py`.
- Examine CLI arguments, environment variable overrides (`TRADING_ENV`, `APCA_API_KEY_ID`), and default values.

### Step 2: Trace Downward Execution Stack
Follow the call graph downward sequentially:
1. **Gatekeepers & Safety Checks**:
   - Where are kill switches read? (e.g., `data/runtime/strategy_kill_switch.json`).
   - What happens if `live_blocked: true`? Does it raise, exit, or fail closed?
2. **State & Account Hydration**:
   - Where does account balance, cash, and positions come from? (`data/system_state.json` or live Alpaca API).
3. **Decision & Sizing Logic**:
   - How is the candidate trade calculated? (e.g., `src/risk/put_credit_optimizer.py`, delta targets, strike selection).
4. **Order Transmission / Dry-Run Interceptor**:
   - If `--dry-run` is active, where is the execution intercepted?
   - In paper mode, what broker client is invoked?
5. **Ledger & Audit Persistence**:
   - What records are appended to `data/trades.json` or `data/put_credit_entries.json`?
   - Are writes atomic?

### Step 3: Document Findings
Produce a structured trace artifact covering:
- **Call Chain**: `Entrypoint` -> `Subsystem A` -> `Subsystem B` -> `Persistence`.
- **Invariants**: What must be true before and after each call.
- **Side Effects**: Files modified, network requests made, processes spawned.
- **Failure Modes**: How exceptions are caught, logged, or propagated.

---

## Example: SPY Put Credit Spread Flow

```mermaid
sequenceDiagram
    autonumber
    participant Op as Operator / Cron
    participant CLI as scripts/spy_put_credit.py
    participant Gate as strategy_kill_switch.json
    participant Opt as put_credit_optimizer.py
    participant Broker as Alpaca Client (Paper)
    participant Ledger as data/trades.json

    Op->>CLI: Execute --dry-run
    CLI->>Gate: Read active_family & live_blocked
    alt live_blocked is True and Env is Live
        Gate-->>CLI: Abort (Hard Safety Rail)
    else Paper or Dry-Run Allowed
        CLI->>Broker: Fetch SPY Underlying Price & Option Chain
        Broker-->>CLI: Option Chain (Quotes, Deltas, Expirations)
        CLI->>Opt: Calculate Sizing & Strike Selection
        Opt-->>CLI: Short/Long Strike Pair & Max Risk
        alt Dry-Run Mode
            CLI->>Op: Print Proposed Order & Expected PnL (No Submit)
        else Active Paper Execution
            CLI->>Broker: Submit Multileg Order
            Broker-->>CLI: Order Confirmation & Fill
            CLI->>Ledger: Append Trade Record & Update State
        end
    end
```
