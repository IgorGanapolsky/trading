# Architecture Research

**Domain:** Automated options trade exit management — Iron Condor lifecycle (SPY)
**Researched:** 2026-02-25
**Confidence:** HIGH (based on direct codebase inspection + domain knowledge)

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         POSITION MONITOR LAYER                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │
│  │  OptionsRiskMon. │  │  PositionManager │  │  AutoCloseBleed.     │  │
│  │  (stop/profit)   │  │  (time/ATR exit) │  │  (crisis containment)│  │
│  └────────┬─────────┘  └────────┬─────────┘  └──────────┬───────────┘  │
│           │                    │                         │              │
├───────────┴────────────────────┴─────────────────────────┴──────────────┤
│                         EXIT ENGINE LAYER                               │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │              ExitDecider (aggregates signals → exit decision)      │  │
│  │  Rules: 50% max profit | 7 DTE time-based | 200% credit stop-loss │  │
│  └───────────────────────────────────┬───────────────────────────────┘  │
├───────────────────────────────────────┴──────────────────────────────────┤
│                         ORDER MANAGER LAYER                             │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │
│  │ AlpacaExecutor   │  │ MandatoryTrade   │  │  TradeSync           │  │
│  │ (order routing)  │  │ Gate (pre-check) │  │  (state persistence) │  │
│  └────────┬─────────┘  └────────┬─────────┘  └──────────┬───────────┘  │
├───────────┴────────────────────┴─────────────────────────┴──────────────┤
│                         P/L TRACKER LAYER                               │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │
│  │  PLValidator     │  │  PerformanceMet. │  │  system_state.json   │  │
│  │  (compliance)    │  │  (win rate, etc.)│  │  (trade_history SST) │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                          Alpaca Paper API
                       (PA3C5AG0CECQ — $100K)
```

### Component Responsibilities

| Component | Responsibility | File | Communicates With |
|-----------|----------------|------|-------------------|
| OptionsRiskMonitor | Checks 50% profit target and stop-loss (200% credit) per position | `src/risk/options_risk_monitor.py` | AlpacaExecutor, OptionsStrategyCoordinator |
| PositionManager | Multi-condition exit evaluation (take-profit, stop-loss, time-decay, ATR) | `src/risk/position_manager.py` | system_state.json (entry dates), AlpacaExecutor |
| AutoCloseBleedingPositions | Crisis containment — emergency close when single position >50% loss or portfolio >25% down | `src/safety/auto_close_bleeding.py` | MandatoryTradeGate.safe_close_position |
| ExitDecider (MISSING) | Aggregates signals from OptionsRiskMonitor + PositionManager, applies iron condor rules (50% profit, 7 DTE) | NOT YET BUILT | All monitor components |
| AlpacaExecutor | Routes close orders to Alpaca via MultiBroker | `src/execution/alpaca_executor.py` | Alpaca API, TradeSync |
| MandatoryTradeGate | Pre-flight validation before any order: ticker whitelist, position size, daily loss limit | `src/safety/mandatory_trade_gate.py` | AlpacaTrader, trading_constants |
| TradeSync | Records every trade to system_state.json → trade_history | `src/observability/trade_sync.py` | system_state.json |
| PLValidator | Decomposes P/L by source, gates projections until 30 completed trades | `src/utils/pl_validator.py` | system_state.json, order data |
| PerformanceMetrics | Win rate, Sharpe, profit factor, drawdown from completed trade list | `src/utils/performance_metrics.py` | PLValidator output |
| DaggrWorkflow | DAG orchestration — runs the full pipeline with gate-keeper nodes | `src/orchestration/daggr_workflow.py` | All components |

## Recommended Project Structure

The exit management system fits cleanly into the existing module hierarchy:

```
src/
├── risk/
│   ├── options_risk_monitor.py   # Position-level profit/stop signals (EXISTS)
│   ├── position_manager.py       # Time-based + ATR exit logic (EXISTS)
│   ├── exit_engine.py            # NEW: Aggregates signals, applies IC rules
│   └── trade_gateway.py          # Pre-trade compliance (EXISTS)
├── safety/
│   ├── mandatory_trade_gate.py   # Pre-execution gate (EXISTS)
│   └── auto_close_bleeding.py    # Emergency exits (EXISTS)
├── execution/
│   └── alpaca_executor.py        # Close order routing (EXISTS)
├── observability/
│   └── trade_sync.py             # Trade recording (EXISTS)
└── utils/
    ├── pl_validator.py           # P/L decomposition (EXISTS)
    └── performance_metrics.py    # Win rate, Sharpe (EXISTS)
```

### Structure Rationale

- **risk/**: All exit decision logic lives here. The gap is `exit_engine.py` — the component that aggregates OptionsRiskMonitor + PositionManager signals into one deterministic close decision per IC.
- **safety/**: Emergency and pre-flight guardrails. Do not merge with risk/ — safety components are always-on circuit breakers, risk components are analytical.
- **execution/**: Only knows HOW to route an order, not WHETHER to exit. Clean boundary.
- **observability/**: Only knows HOW to record a trade outcome. Clean boundary.

## Architectural Patterns

### Pattern 1: Signal Aggregation (ExitDecider)

**What:** A single function that takes signals from multiple monitors and returns one boolean + reason for closing.

**When to use:** When multiple components can independently flag a position for exit. Prevents duplicate close orders.

**Trade-offs:** Single point of authority is simpler than distributed exit checks; slight coupling between monitor components.

**Example:**
```python
# src/risk/exit_engine.py (TO BUILD)
def should_exit_iron_condor(
    position: ICPosition,
    options_risk: OptionsRiskMonitor,
    position_mgr: PositionManager,
    current_prices: dict[str, float],
) -> tuple[bool, str]:
    """
    Deterministic iron condor exit decision.
    Priority: 1=stop-loss, 2=DTE, 3=profit-target
    """
    # Rule 1: Stop-loss (200% of credit received)
    should_close, reason = options_risk.should_close_position(position.symbol)
    if should_close and "stop-loss" in reason.lower():
        return True, f"STOP_LOSS: {reason}"

    # Rule 2: 7 DTE exit (avoid gamma risk)
    dte = (position.expiration - date.today()).days
    if dte <= 7:
        return True, f"DTE_EXIT: {dte} DTE remaining"

    # Rule 3: 50% profit target
    if should_close and "profit" in reason.lower():
        return True, f"PROFIT_TARGET: {reason}"

    return False, "HOLD"
```

### Pattern 2: DAG Node Integration

**What:** Wrap the ExitDecider as a `gate_keeper` node in `daggr_workflow.py` that runs before each new entry cycle.

**When to use:** When exit management needs to run on a schedule independent of trade entry.

**Trade-offs:** Clean separation of concerns. Exit checks run even when no new entry is made. Slight overhead of DAG node framework.

**Example:**
```python
# In daggr_workflow.py
workflow.add_node(
    "exit_check",
    check_and_close_exits,   # wraps ExitDecider
    "gate_keeper",
    cache_enabled=False,     # Never cache — always fresh prices
    timeout_seconds=60.0,
)
workflow.add_node(
    "risk_gate",
    analyze_risk,
    "gate_keeper",
    dependencies=["exit_check"],  # Run exits before new entries
)
```

### Pattern 3: State Persistence for Exit Tracking

**What:** Iron condor positions span 24+ days. Exit tracking state must survive process restarts. The pattern is: write exit-relevant state to `data/system_state.json` on every update.

**When to use:** Any per-position metadata (entry credit received, leg symbols, DTE at entry) that is needed for exit decisions.

**Trade-offs:** JSON file creates a single-write bottleneck, but at 5 concurrent ICs this is negligible. The PositionManager already implements this pattern correctly.

## Data Flow

### Exit Decision Flow (Per Iron Condor Position)

```
Alpaca API (live position prices)
    ↓
Position Price Update
    ↓
OptionsRiskMonitor.update_position_price()   ← for each IC leg
    ↓
OptionsRiskMonitor.run_risk_check()
    ├── profit_exits[]   (50% of max credit hit)
    └── stop_loss_exits[]  (200% of credit = loss threshold)
    ↓
ExitDecider.should_exit_iron_condor()        ← AGGREGATOR (to build)
    ↓ (if exit = True)
MandatoryTradeGate.validate_trade_mandatory()  ← pre-close safety check
    ↓
AlpacaExecutor.close_position()              ← 4-leg IC close (buy-to-close all legs)
    ↓
TradeSync.sync_trade_outcome()              ← records P/L to system_state.json
    ↓
PLValidator.validate_pl_report()            ← updates win count, gating projections
    ↓
PerformanceMetrics.calculate_all_metrics()  ← updates Sharpe, win rate, profit factor
```

### DTE Monitoring Flow (Scheduled, Daily)

```
GitHub Actions (cron: market open daily)
    ↓
exit_manager_workflow.yml
    ↓
ExitDecider.check_all_positions_dte()      ← scans all open ICs for DTE <= 7
    ↓ (if DTE <= 7)
AlpacaExecutor.close_position()
    ↓
TradeSync.sync_trade_outcome()
```

### State Management

```
system_state.json (SINGLE SOURCE OF TRUTH)
    ├── trade_history[]           → PLValidator reads for win count
    ├── position_entries{}        → PositionManager reads for time-based exits
    ├── open_iron_condors[]       → ExitDecider reads for DTE checks (TO ADD)
    └── equity_curve[]            → PerformanceMetrics reads for Sharpe
```

### Key Data Flows

1. **Profit target exit:** OptionsRiskMonitor detects credit spread value dropped to 50% of entry → ExitDecider flags → AlpacaExecutor places 4-leg buy-to-close → TradeSync records win.
2. **DTE exit:** Daily cron checks expiration dates → any IC at 7 DTE → close regardless of P/L to avoid gamma risk (LL-268).
3. **Stop-loss exit:** OptionsRiskMonitor detects spread cost = 200% of credit received → CRITICAL priority → close immediately → TradeSync records loss.
4. **P/L attribution:** PLValidator.validate_pl_report() gates all projections until 30 completed iron condor trades exist (current: 2/30 per profit_target_report.json).

## Integration Points

### Missing Component: Iron Condor Exit Engine

The most critical gap is that no single component integrates the three iron condor exit rules into one decision loop with DTE tracking:

| Rule | Threshold | Current Owner | Status |
|------|-----------|---------------|--------|
| Profit target | 50% of max credit | OptionsRiskMonitor (75% configured, needs adjustment) | EXISTS but wrong threshold |
| Time exit | 7 DTE | No automated check | MISSING |
| Stop-loss | 200% of credit | OptionsRiskMonitor (100% configured, needs adjustment) | EXISTS but wrong threshold |

The `OptionsRiskMonitor` has `DEFAULT_STOP_LOSS_MULTIPLIER = 1.0` (100% of credit) and `DEFAULT_PROFIT_TARGET_PCT = 0.75` (75% of credit). Per PROJECT.md the rules should be 50% profit target and 200% stop-loss. Both constants need adjustment AND a DTE check needs to be wired in.

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Alpaca API | REST via `alpaca-trade-api` through AlpacaTrader | Options require Level 2 approval; paper account PA3C5AG0CECQ confirmed |
| GitHub Actions | Scheduled cron workflows → Python scripts | sync-system-state.yml already syncs; exit manager needs its own workflow |
| yfinance | Price fallback for DTE/delta calculations | Used by options_analysis.py; rate-limited — not reliable for real-time exit checks |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| ExitEngine → AlpacaExecutor | Direct function call | Exit engine calls `executor.close_position(symbol, qty)` |
| ExitEngine → MandatoryTradeGate | Pre-close validation via `validate_trade_mandatory()` | Even close orders must pass the gate |
| ExitEngine → TradeSync | Writes outcome after close confirmation | Must confirm fill before recording |
| PositionManager → system_state.json | Atomic JSON write (temp file + rename) | Already implemented correctly |
| PLValidator → ExitEngine | Read-only: checks completed trade count before projections | Gate: do not project until 30 completed ICs |

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 3-5 concurrent ICs (current) | JSON state file is sufficient. Single-process exit check on schedule works. |
| 5-10 concurrent ICs (Phase 2) | Add a dedicated `open_positions_registry` dict in system_state.json. JSON write contention possible if exit check and workflow run concurrently — add file lock. |
| 10+ ICs across weekly/monthly expiry (Phase 3) | Consider SQLite instead of JSON for concurrent reads. Add per-expiry-cycle tracking to decouple monitoring per DTE bucket. |

### Scaling Priorities

1. **First bottleneck:** Missing DTE exit automation. At 3 ICs, manually watching DTE is feasible. At 5+ ICs with overlapping expiries it breaks. The 7-DTE check must be automated before scaling to 5.
2. **Second bottleneck:** P/L attribution accuracy. PLValidator.validate_pl_report() currently requires 30 closed trades before projections. With automated exits, this gate will clear faster.

## Anti-Patterns

### Anti-Pattern 1: Distributed Exit Logic

**What people do:** Each agent/component independently calls `close_position()` when it detects a threshold breach.

**Why it's wrong:** Two components (OptionsRiskMonitor + AutoCloseBleedingPositions) independently detect the same condition → duplicate close orders → Alpaca rejects second close with "position not found" error → silent failure, no audit trail.

**Do this instead:** Funnel all exit decisions through a single ExitDecider. Components emit signals (should_close=True, reason), ExitDecider is the only caller of `close_position()`.

### Anti-Pattern 2: Caching Exit Decisions

**What people do:** Cache the result of `should_close_position()` to avoid repeated API calls.

**Why it's wrong:** The DaggrWorkflow already has `cache_enabled=False` on the `trade_decision` node for this reason. Options prices move continuously. A 10-minute-old "HOLD" signal is stale by definition.

**Do this instead:** Never cache exit check results. Fetch fresh prices from Alpaca before every exit evaluation. The workflow already enforces this via `cache_enabled=False`.

### Anti-Pattern 3: Conflating Entry and Exit Thresholds

**What people do:** Use the same `ExitConditions` dataclass for both equities and iron condors (PositionManager currently does this for equities with 15% take-profit / 8% stop-loss).

**Why it's wrong:** Iron condor profit targets are defined as % of credit received, not % of price move. A 15% price target is meaningless for a spread that collected $150 credit.

**Do this instead:** Keep `OptionsRiskMonitor` as the authority for iron condor exits (credit-relative thresholds). Use `PositionManager` only for equity positions. Route IC symbols to `OptionsRiskMonitor`, equity symbols to `PositionManager`.

### Anti-Pattern 4: Recording P/L Before Fill Confirmation

**What people do:** Call `TradeSync.sync_trade_outcome()` immediately after placing a close order.

**Why it's wrong:** The order may not fill (market closed, liquidity issue, rejection). Recording unfilled P/L inflates the win count and corrupts PLValidator's 30-trade gate.

**Do this instead:** Poll Alpaca order status, confirm `filled_at` is set and `filled_qty > 0`, THEN call sync. AlpacaExecutor already has retry logic that should be extended to cover close confirmations.

## Build Order (Component Dependencies)

Based on the dependency graph, the correct implementation sequence is:

```
1. ExitEngine (src/risk/exit_engine.py)
   - Depends on: OptionsRiskMonitor (EXISTS), PositionManager (EXISTS)
   - Provides: Single exit decision API for steps 2, 3

2. DTE Check Integration
   - Depends on: ExitEngine (step 1), Alpaca positions API
   - Provides: Automated 7-DTE exit without manual intervention

3. ExitEngine → DaggrWorkflow Node
   - Depends on: ExitEngine (step 1), DTE Check (step 2)
   - Provides: Exit logic running before every new-entry cycle

4. OptionsRiskMonitor Threshold Fix
   - Depends on: Nothing (standalone constant change)
   - Change: stop_loss_multiplier 1.0 → 2.0, profit_target_pct 0.75 → 0.50
   - Can parallelize with step 1

5. Scheduled Exit Workflow (.github/workflows/exit_manager.yml)
   - Depends on: Steps 1-3
   - Provides: Daily automated exit scan at market open

6. PLValidator Integration
   - Depends on: Steps 1-5 generating completed trades
   - Provides: Accurate win rate after 30+ trades close
```

## Sources

- `src/risk/options_risk_monitor.py` — directly inspected, constants at lines 19-20
- `src/risk/position_manager.py` — directly inspected, ExitConditions at lines 64-112
- `src/safety/auto_close_bleeding.py` — directly inspected
- `src/orchestration/daggr_workflow.py` — directly inspected, node types and cache settings
- `src/safety/mandatory_trade_gate.py` — directly inspected
- `src/observability/trade_sync.py` — directly inspected, CANONICAL data flow comment
- `src/utils/pl_validator.py` — directly inspected, MIN_TRADES_FOR_PROJECTION = 30
- `src/utils/performance_metrics.py` — directly inspected
- `.planning/PROJECT.md` — requirements: 50% profit target, 7 DTE exit, 200% credit stop-loss
- `reports/profit_target_report.json` — confirmed 2/30 completed trades as of 2026-02-25

---
*Architecture research for: Automated options trade exit management — Iron Condor (SPY)*
*Researched: 2026-02-25*
