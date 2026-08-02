# Pitfalls Research

**Domain:** Automated options exit management — iron condor lifecycle tracking, profit-taking automation, position monitoring for an existing Alpaca paper trading system.
**Researched:** 2026-02-25
**Confidence:** HIGH (evidence drawn directly from this codebase's own incident history, lesson-learned comments, and code-level guard implementations)

---

## Critical Pitfalls

### Pitfall 1: Closing Legs Individually Instead of as a Multi-Leg Unit

**What goes wrong:**
When an iron condor exit fires, the system submits four separate market orders (one per leg) rather than a single atomic MLeg order. If any leg fails or fills at a different time, you are left with orphan legs: a naked short put, a broken spread, or a position that no longer has defined risk.

**Why it happens:**
Exit logic is often written by iterating over positions and calling `close_position(symbol)` on each. The original position entry may have been a multi-leg order, but the symmetry is not preserved on the exit side. Developers reach for the simplest per-leg close and do not notice the problem until an orphan accumulates losses.

**Evidence from this codebase:**
The `close_iron_condor()` function in `scripts/manage_iron_condor_positions.py` has an explicit comment: "FIX Jan 27, 2026: Changed from individual leg orders to MLeg (multi-leg) order. Previous bug: Individual close orders destroyed iron condor structure, leaving orphan legs that caused losses. MLeg ensures all legs close together or not at all." Multiple emergency workflows exist (`close-orphan-position.yml`, `close-orphan-spy-puts.yml`, `fix-broken-spread.yml`) that are direct artifacts of this class of failure.

**How to avoid:**
All iron condor exits MUST use `OrderClass.MLEG` with `OptionLegRequest` for each leg. Never iterate legs and close individually. The MLeg order is atomic: all legs fill or none do. Add a CI test that asserts no `close_position` call exists for OCC option symbols outside the MLeg path.

**Warning signs:**
- Workflows named `close-orphan-*`, `fix-broken-spread`, `emergency-close-options` appearing in the repository
- Position count for an expiry is not a multiple of 4 (iron condors always have exactly 4 legs)
- `unrealized_pl` on individual legs is extremely asymmetric without a corresponding profit on the other side

**Phase to address:** Exit Execution phase (any phase that first introduces automated close orders)

---

### Pitfall 2: The Monitoring Loop Runs but the Exit Does Not Execute (Dry-Run Default)

**What goes wrong:**
The position monitor fires on schedule, identifies positions that meet exit criteria, logs "EXIT TRIGGERED," but no order is submitted because `dry_run=True` is the default. Profit targets and stop-losses are detected but not acted upon. The system appears to be managing positions — it is not.

**Why it happens:**
Dry-run defaults are added during development for safety and never flipped to live execution once the code ships. CI passes because the code runs without errors. The scheduler runs, the logs look correct, but zero exits happen. This directly maps to the current system state: 3 open ICs, 1 completed trade in 3 weeks.

**Evidence from this codebase:**
`src/safety/auto_close_bleeding.py` line 228: `dry_run: bool = True` is the default parameter in `execute_auto_close()`. The `manage_iron_condor_positions.py` workflow step calls `python3 scripts/manage_iron_condor_positions.py` with no `--dry-run` flag, but the underlying `close_iron_condor()` default also accepts `dry_run` as a parameter. Any caller that omits the flag silently does nothing.

**How to avoid:**
Require `dry_run` to be explicitly passed at every call site — never use a default. In production workflow steps, pass `--live` as a required positional argument that must be present; absence of `--live` causes a hard error rather than a silent no-op. Add a CI integration test that mocks the Alpaca client and verifies that `close_iron_condor` is called with `dry_run=False` when an exit condition is met.

**Warning signs:**
- Exit conditions are logged as triggered but no orders appear in Alpaca order history
- `exits_triggered > 0` but `exits_executed == 0` in system state `ic_position_management`
- Win rate stays at 0% despite the monitor running for weeks

**Phase to address:** Exit Execution phase, before any monitoring workflow is declared production-ready

---

### Pitfall 3: P/L Attribution — Conflating Account Equity Change with Trading Performance

**What goes wrong:**
The system reports "+$864 this week" as iron condor performance. In reality, the equity change includes interest on idle cash, paper gains from existing ETF positions, and Alpaca paper account quirks. When a projection is built on this number, the return rate is inflated by 5-10x versus actual IC-generated income.

**Why it happens:**
Equity-delta is the easiest number to retrieve from the broker API. It requires zero decomposition. Developers reach for it because it looks like profit. The problem surfaces only when the system starts claiming 4%/month returns from 7 days of data with 0 completed iron condors.

**Evidence from this codebase:**
`src/utils/pl_validator.py` was created specifically to address this: "Root cause: Claude made incorrect P/L projections by: 1. Projecting 4.3%/month from 7 days of data; 2. Misattributing pre-existing position gains to iron condor trading." The constant `MIN_TRADES_FOR_PROJECTION = 30` hard-blocks projections until 30 completed iron condors exist.

**How to avoid:**
Every P/L claim must pass through `validate_pl_report()` in `src/utils/pl_validator.py`. Never present equity delta as trading performance. Build a decomposed attribution layer: `equity_change = ic_realized_pl + cash_interest + unrealized_mark_to_market`. Display these as separate line items. Block projection endpoints at the API layer until `completed_iron_condors >= 30`.

**Warning signs:**
- Dashboard shows positive P/L without any completed trades
- "Monthly return" is computed by annualizing < 2 weeks of data
- P/L percentage jumps on days when no IC legs were closed

**Phase to address:** Trade Lifecycle Tracking phase, before any reporting or projection feature is built

---

### Pitfall 4: Race Condition — Two Monitors Submit Competing Close Orders for the Same Position

**What goes wrong:**
Two workflows (`iron-condor-guardian.yml` runs every 30 minutes, `manage-iron-condor-positions.yml` runs hourly) both detect the same exit condition within the same window and both submit close orders for the same IC. The second order attempts to close a position that no longer exists and either fails with an API error or creates a net-short position.

**Why it happens:**
Exit monitoring is often developed as a single workflow and then duplicated or supplemented with a secondary guardian. Without a shared lock or idempotency key, both fire independently during overlapping windows.

**Evidence from this codebase:**
The `manage-iron-condor-positions.yml` workflow has an explicit concurrency group: `group: global-trade-execution` with `cancel-in-progress: false`. The `iron-condor-guardian.yml` workflow does NOT have this concurrency group. Both run during market hours. The comment in `manage-iron-condor-positions.yml` references "LL-281 race condition fix" — this was a post-incident lesson.

**How to avoid:**
Apply the same concurrency group (`global-trade-execution`) to every workflow that can submit or close orders. Use the `concurrency: cancel-in-progress: false` setting so the in-flight execution completes rather than being killed mid-order. Before submitting a close order, verify the position still exists (re-fetch from broker). After a successful close, write an idempotency record (`data/closed_ics.json`) keyed on `expiry_date + underlying` so subsequent runs skip already-closed positions.

**Warning signs:**
- Alpaca API errors of type "position not found" or "insufficient quantity" on close orders
- IC leg count drops below 4 for an expiry without a corresponding profit/loss record
- Duplicate entries in trade trajectory log for the same expiry

**Phase to address:** Position Monitoring phase, as soon as multiple monitoring workflows coexist

---

### Pitfall 5: No Entry-Credit Record — Exit Cannot Compute P/L as % of Credit

**What goes wrong:**
The exit condition for an iron condor is "close at 50% of credit received." If the credit received at entry was not persisted, the monitor cannot determine the threshold. It defaults to comparing current mark-to-market against entry price, which produces incorrect percentages for multi-leg strategies where the net credit is spread across four legs with different signs.

**Why it happens:**
Entry recording is treated as optional metadata ("nice to have"). The trade gateway records the order submission but not the net credit received. When the monitor runs hours later in a separate process, it has no access to the entry credit without querying historical fills.

**Evidence from this codebase:**
`scripts/iron_condor_guardian.py` uses `IC_ENTRIES_FILE = Path("data/ic_entries.json")` to persist entry credits separately. `group_iron_condors()` in `manage_iron_condor_positions.py` recomputes credit from live position data by summing `avg_entry_price * qty` for short legs — but this only works if `avg_entry_price` is populated in the Alpaca positions response (it is on paper, but can be stale or zero on fills with complex routing). `check_exit_conditions()` short-circuits with "No credit tracked" if `credit <= 0`, resulting in no exit being triggered even when the position is at 80% profit.

**How to avoid:**
At the moment an iron condor is opened (immediately after the MLeg order fills), record the net credit to a persistent store: `data/ic_entries.json` keyed by `underlying + expiry_date`. Include: credit per spread, number of contracts, entry timestamp, target profit dollar amount, stop-loss dollar amount. The monitor reads this file — never recomputes from live position data alone. Add an alert if the monitor finds an option position with no corresponding entry record.

**Warning signs:**
- Logs show "No credit tracked" for any IC expiry
- `credit_received` is 0 in IC grouping output
- Profit target is never triggered even when positions are deep in-the-money for sellers

**Phase to address:** Exit Execution phase — credit persistence must be implemented before exit logic is wired up

---

### Pitfall 6: DTE Calculation Uses Wrong Timezone and Counts Calendar Days, Not Trading Days

**What goes wrong:**
`calculate_dte()` subtracts today's date from expiry using `datetime.now()` (local or UTC). Options expire at market close (4:00 PM ET) on the expiration date. A monitor running at 9:00 AM ET on expiry Friday calculates DTE = 0 and exits immediately; a monitor running UTC+0 on Thursday night calculates DTE = 1 when ET trading is already over. Either causes an exit at the wrong time or a missed exit that enters gamma risk territory.

**Why it happens:**
Timezone handling is tedious. Developers use `datetime.now()` and assume it is close enough. The error is invisible in backtests that use daily close prices and only surfaces in live intraday monitoring.

**Evidence from this codebase:**
`scripts/manage_iron_condor_positions.py` `calculate_dte()` uses `datetime.now()` with no timezone. `scripts/iron_condor_guardian.py` uses `ZoneInfo("America/New_York")` correctly but only for the guardian path. Two separate implementations exist with different timezone handling.

**How to avoid:**
Create a single canonical `calculate_dte(expiry_str: str) -> int` in `src/utils/calendar_validation.py` that always uses `America/New_York` timezone. Return `0` when expiry day is today (regardless of time of day) — iron condors should always be closed before the expiration date, not on it. Use this single function everywhere. Write a unit test with explicit ET timezone assertions.

**Warning signs:**
- DTE logged as negative numbers (position held past expiry)
- "7 DTE exit" triggered at 8 DTE or 6 DTE depending on time of day the monitor runs
- Inconsistent DTE values across different scripts for the same position

**Phase to address:** Position Monitoring phase, before DTE-based exit logic goes live

---

### Pitfall 7: Treating "Monitored" as Equivalent to "Managed"

**What goes wrong:**
The system has monitoring code that detects exit conditions and emits log lines or updates `system_state.json`. A human reviewing the logs concludes the system is actively managing positions. In reality, the monitoring code only reads and reports — it never submits orders. Position management appears active; actual exits never happen.

**Why it happens:**
The monitoring component and the execution component are often built by different agents or in different phases. The monitoring component is completed first and declared "working." The execution wiring is deferred or never added. The gap between "detected exit condition" and "submitted close order" is invisible unless you check Alpaca order history directly.

**Evidence from this codebase:**
`src/risk/options_risk_monitor.py` has `run_risk_check()` which returns a dict with `stop_loss_exits` and `profit_exits`. It does not submit any orders. `src/risk/position_manager.py` `manage_all_positions()` returns a list of exit signals — it does not submit any orders. Both classes require a separate caller to take the list and actually execute. The `OptionsRiskMonitor.run_risk_check(executor=None)` signature shows `executor` is optional and defaults to None, meaning the execution path is never invoked unless explicitly wired.

**How to avoid:**
Draw a hard architectural boundary: the monitoring component produces `List[ExitSignal]` and the execution component consumes `List[ExitSignal]` and submits orders. The integration point must be tested with a mock broker that asserts orders were submitted. Add a CI test that runs the full pipeline end-to-end: inject a position at 51% profit → assert a close order was submitted to the mock broker.

**Warning signs:**
- Exit signals appear in logs but Alpaca order history shows no corresponding fills
- `OptionsRiskMonitor.run_risk_check(executor=None)` is called without providing an executor
- `manage_all_positions()` result is logged but the return value is not iterated to submit orders

**Phase to address:** Exit Execution phase — the monitoring-to-execution wiring is the single most critical integration point

---

### Pitfall 8: Inconsistent Profit Target Definitions Across Modules

**What goes wrong:**
`src/risk/options_risk_monitor.py` uses `DEFAULT_PROFIT_TARGET_PCT = 0.75` (75%). `scripts/manage_iron_condor_positions.py` uses `profit_target_pct: 0.50` (50%). `src/risk/position_manager.py` uses `(0.50, 1.00, 45)` for options. The GRPO optimal exit from `CLAUDE.md` is 29%. Four different profit targets exist simultaneously. The system closes positions at inconsistent thresholds depending on which code path fires first.

**Why it happens:**
Thresholds are defined per-module rather than in a single constants file. Each module developer picks a reasonable number without checking what the other modules use. When GRPO updates the optimal parameter, it updates the GRPO config but not the four hardcoded values scattered across modules.

**Evidence from this codebase:**
`src/constants/trading_thresholds.py` exists but the profit target constant is not consistently referenced from it across all exit paths. `src/risk/options_risk_monitor.py` defines `DEFAULT_PROFIT_TARGET_PCT = 0.75` locally. `IC_EXIT_CONFIG` in `scripts/manage_iron_condor_positions.py` defines `profit_target_pct: 0.50` locally.

**How to avoid:**
Move ALL exit thresholds to a single source of truth: `src/core/trading_constants.py` or `src/constants/trading_thresholds.py`. Define `IC_PROFIT_TARGET_PCT`, `IC_STOP_LOSS_PCT`, `IC_EXIT_DTE` there. All modules import from this file — no local definitions. GRPO writes its optimized parameters to this file (or a config override layer that the constants module reads). Add a CI lint rule that fails if any `.py` file defines a float literal equal to 0.50 or 0.75 outside of the constants file in the context of profit targets.

**Warning signs:**
- Grep for `profit_target` returns different float values in different files
- GRPO trains to 29% optimal exit but positions are being closed at 50% or 75%
- Win rate and expected value calculations disagree with actual closed trade outcomes

**Phase to address:** Trade Lifecycle Tracking phase and Exit Execution phase — fix before adding any new exit path

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| `dry_run=True` default on exit functions | Safe during development | Silently prevents all exits in production | Never — require explicit flag |
| Per-module profit target constants | Fast to write | Diverges from GRPO-optimized value; inconsistent behavior | Never — use single constants file |
| Recomputing credit from live position data | No persistent storage needed | Fails when `avg_entry_price` is stale or zero | Never — persist at entry |
| `datetime.now()` without timezone for DTE | Simple code | Wrong exit timing across timezones | Never for live monitoring |
| Individual leg close orders instead of MLeg | Simpler API call | Creates orphan legs, undefined risk | Never for iron condors |
| Returning exit signals without executing them | Clean separation | Monitoring-execution gap; positions never close | Only during unit testing with mock brokers |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Alpaca `get_all_positions()` | Assume `avg_entry_price` is always populated | Verify it is non-zero before using for credit calculation; fall back to `ic_entries.json` |
| Alpaca MLeg orders | Pass `TimeInForce` to MLeg option order | TimeInForce is not supported for options MLeg orders (Alpaca constraint); omit it |
| Alpaca paper account | Assume paper fills behave identically to live | Paper fills can have zero `current_price` for deep OTM options; handle null prices |
| GitHub Actions scheduling | Assume cron fires exactly on schedule | Actions can be delayed 5-15 minutes during high load; never rely on exact fire time for DTE calculation — recalculate at runtime |
| `system_state.json` writes | Write directly from multiple processes | Use atomic write (write to `.tmp`, then rename) to prevent corruption; `position_manager.py` already does this — follow the same pattern |
| Concurrency groups in GitHub Actions | Apply to new monitoring workflows only | Apply `global-trade-execution` concurrency group to ALL workflows that submit or close orders, not just the primary one |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Fetching all positions on every monitor tick | API rate limit errors during volatile markets | Cache positions for 60 seconds; only re-fetch on cache miss | At 5+ concurrent ICs with 30-minute monitor frequency |
| Recomputing option Greeks on every DTE check | Slow monitor runs, potential timeout in CI | Cache Greeks with 5-minute TTL; DTE only needs date arithmetic | Immediately if Greeks are fetched from a paid API with per-call pricing |
| Loading full `system_state.json` to update a single field | Concurrent write corruption | Use atomic write pattern; never partial-update JSON in-place | At hourly sync + exit monitor + GRPO training running concurrently |
| OCC symbol parsing via string slicing with fixed offsets | Fails on 4-letter underlyings (e.g., SPXW) | Use a proper OCC symbol parser with length detection | When XSP/SPX migration happens (planned in PROJECT.md) |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Logging Alpaca API responses verbatim | Account numbers, positions, and order IDs in GitHub Actions logs (public repo) | Sanitize log output; never log raw API response objects |
| Hardcoding `paper=True` in scripts | Accidental live execution if flag is flipped during XSP/SPX migration | Load paper/live mode from an environment variable with no default; fail loudly if unset |
| Writing credentials fallback chain with multiple env var names | Silently uses wrong account credentials if primary vars are missing | Validate exactly one set of credentials is present; log which account is active at startup |

---

## "Looks Done But Isn't" Checklist

- [ ] **Exit automation:** Logs show "EXIT TRIGGERED" — verify Alpaca order history shows a corresponding filled close order, not just a logged detection
- [ ] **Profit target:** 50% profit target is defined — verify it references the single constants file, not a local float literal
- [ ] **DTE exit:** 7 DTE exit is implemented — verify timezone is `America/New_York` and the test asserts behavior on expiry Friday before 4 PM ET
- [ ] **MLeg close:** Exit submits a close order — verify it uses `OrderClass.MLEG`, not four individual `MarketOrderRequest` calls
- [ ] **Credit persistence:** Entry credit is recorded — verify `data/ic_entries.json` is written immediately after MLeg entry order fills, before the monitor first runs
- [ ] **Race condition guard:** Concurrency group is set — verify `global-trade-execution` group appears in the `concurrency:` block of EVERY workflow that touches orders, not just the primary one
- [ ] **Win/loss record:** Trade is closed — verify `record_trade_outcome()` is called and the trade appears in `data/feedback/trade_trajectories.jsonl` with `won: true/false`
- [ ] **P/L attribution:** Dashboard shows positive return — verify it is sourced from closed IC realized P/L, not raw equity delta

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Orphan legs from individual close orders | HIGH | Run `close-orphan-position.yml` manually; verify leg count returns to 0 for that expiry; record the incident in lessons-learned |
| Dry-run default left in production | MEDIUM | Flip flag, re-run monitor, verify orders submitted; check if profit window was missed during the blind period |
| P/L misattribution presented to CEO | MEDIUM | Re-run `validate_pl_report()` with correct data; correct all dashboard numbers; add `MIN_TRADES_FOR_PROJECTION` gate to reporting endpoint |
| Race condition double-close | LOW | Second order fails at API level (position not found); verify no net-short position was created; add idempotency key |
| Wrong profit target threshold | MEDIUM | Identify which module fired the exit; update to single constants file; re-evaluate whether remaining open positions should have been closed earlier |
| DTE miscalculation held position past expiry | HIGH | Position expires worthless or triggers assignment; immediate broker cleanup; record severity-5 lesson |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Individual leg close (Pitfall 1) | Exit Execution | CI test: assert `OrderClass.MLEG` on any close touching OCC symbols |
| Dry-run default silent no-op (Pitfall 2) | Exit Execution | Integration test: mock broker asserts close order was submitted |
| P/L misattribution (Pitfall 3) | Trade Lifecycle Tracking | CI test: `validate_pl_report()` is called before any projection endpoint |
| Race condition double-close (Pitfall 4) | Position Monitoring | Verify `global-trade-execution` concurrency group on all order-submitting workflows |
| Missing entry credit record (Pitfall 5) | Exit Execution | CI test: after MLeg entry, assert `data/ic_entries.json` contains the expiry key |
| DTE timezone error (Pitfall 6) | Position Monitoring | Unit test: assert DTE = 0 when called at 9 AM ET on expiry date |
| Monitoring without execution (Pitfall 7) | Exit Execution | End-to-end test: position at 51% profit → assert filled close order in mock broker |
| Inconsistent profit targets (Pitfall 8) | Trade Lifecycle Tracking | Lint rule: no float literals for profit/stop thresholds outside `trading_constants.py` |

---

## Sources

- `scripts/manage_iron_condor_positions.py` — "FIX Jan 27, 2026" comment on MLeg atomic close (Pitfall 1)
- `src/safety/auto_close_bleeding.py` — `dry_run=True` default (Pitfall 2)
- `src/utils/pl_validator.py` — docstring citing the Feb 6, 2026 P/L misattribution root cause (Pitfall 3)
- `.github/workflows/manage-iron-condor-positions.yml` — "LL-281 race condition fix" comment (Pitfall 4)
- `scripts/iron_condor_guardian.py` — `IC_ENTRIES_FILE` pattern for credit persistence (Pitfall 5)
- `scripts/manage_iron_condor_positions.py` vs `scripts/iron_condor_guardian.py` — DTE timezone discrepancy (Pitfall 6)
- `src/risk/options_risk_monitor.py` and `src/risk/position_manager.py` — executor=None default (Pitfall 7)
- `src/risk/options_risk_monitor.py` (0.75), `scripts/manage_iron_condor_positions.py` (0.50), `src/risk/position_manager.py` (0.50), `.claude/CLAUDE.md` (29% GRPO optimal) — four different profit targets (Pitfall 8)
- Emergency workflows: `close-orphan-position.yml`, `close-orphan-spy-puts.yml`, `fix-broken-spread.yml`, `emergency-close-options.yml` — direct artifacts of Pitfall 1 recurrence
- `.planning/PROJECT.md` — active requirements and context

---
*Pitfalls research for: Automated options exit management — iron condor lifecycle on Alpaca paper trading*
*Researched: 2026-02-25*
