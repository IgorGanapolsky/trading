# 📈 Options Profit Roadmap – Targeting $10/Day

**Date:** 2025-12-02
**Owner:** Claude CTO
**Scope:** Phil Town Rule #1 workflow + covered calls/puts stack

---

## 1. Baseline Reality Check

- `data/system_state.json` shows **$0 allocated to options** and zero open stock positions → no covered-call inventory.
- `RuleOneOptionsStrategy` can emit signals, but nothing consumes them and we had no tooling to translate premiums into a daily run-rate.
- Latest automation artifacts stop at 2025-11-11; no evidence that options signals have been reviewed since code landed.
- Without a pacing model we cannot prove or falsify the CEO mandate: “earn $10/day reliably via options income”.

---

## 2. Gaps Identified

| Area | Observation | Impact |
| --- | --- | --- |
| Signal telemetry | `RuleOneOptionsStrategy` persisted raw JSON but lacked days-to-expiry metadata and no aggregation layer. | Could not compute premium per day or contract sizing → no path to $10/day proofs. |
| Planning | No artifact translated existing signals into “target vs actual” premium tracking. | CEO lacks single answer to “how far are we from $10/day?” |
| Execution | Options toolkit was disconnected from daily automation; no CLI to review/plan. | Manual eyeballing required, violating automation mandate. |
| Capital plan | Options acceleration doc existed but not linked to actionable telemetry. | Hard to prioritize accumulation vs. premium selling. |

---

## 3. Enhancements Implemented Today

1. **Signal telemetry upgrade**
   - Added `days_to_expiry` to every `RuleOneOptionsSignal` instance and snapshot serialization.
   - Ensures downstream analytics can calculate daily premium pacing without re-fetching option chains.

2. **Options Profit Planner (`src/analytics/options_profit_planner.py`)**
   - Normalizes put/call signals (live objects or JSON snapshots).
   - Computes premium per contract/day, total run-rate, and monthly/annual projections.
   - Highlights the shortfall vs configurable daily target (defaults to **$10/day**).
   - Recommends how many additional contracts (and on which symbol) are required to close the gap.

3. **CLI Workflow (`scripts/options_profit_planner.py`)**
   - `PYTHONPATH=src python3 scripts/options_profit_planner.py`
   - Reads the latest snapshot or optionally triggers a fresh Rule #1 scan (if APIs/network available).
   - Persists summarized plans under `data/options_signals/options_profit_plan_*.json`.
   - Human-readable console output so CEO can see “daily run-rate vs $10 target” instantly.

4. **Audit Trail**
   - `data/options_signals/` now tracked in git (via `.gitkeep`) so plans + signals live beside system state.

5. **Testing Coverage**
   - `tests/test_options_profit_planner.py` validates pacing math, snapshot handling, and persistence.

---

## 4. Path to Reliable $10/Day Options Income

1. **Daily Profit Tracking**
   - Run the planner after each `RuleOneOptionsStrategy` cycle:
     ```bash
     PYTHONPATH=src python3 scripts/options_profit_planner.py --target-daily 10
     ```
   - The generated JSON under `data/options_signals/` feeds dashboards / reports and proves whether we are pacing toward $10/day.

2. **Capital Accumulation Alignment**
   - Link `OptionsAccumulationStrategy` (NVDA focus) output into planner notes once ≥50 shares exist.
   - Planner already surfaces “gap to target”; use it to justify temporarily raising the accumulation budget when gap > $8/day.

3. **Signal Quality Gates**
   - Keep IV-rank (<40) and conservative delta ranges (20–25) enforced in `rule_one_options.py`.
   - With `days_to_expiry` captured, we can now reject any signal whose pacing < $1/contract/day, ensuring each fill contributes meaningfully to the $10 target.

4. **Automation Hook**
   - Add the planner CLI to the GitHub Actions daily workflow after options signals are generated.
   - Publish `options_profit_plan_*.json` to dashboard/Slack so leadership sees premium projections with zero manual work.

5. **Escalation Rule**
   - If `gap_to_target > $5` for 3 consecutive planner runs, trigger:
     - Increase `OPTIONS_ACCUMULATION_DAILY` budget.
     - Allow planner recommendation to auto-open additional puts/calls (once Alpaca options approval confirmed).

---

## 5. Theta Harvest Automation (Dec 2025)

- **Execution bridge**: `ThetaHarvestExecutor` now produces executable orders and streams them through `ExecutionAgent.submit_option_order()` once the equity gate hits **$5k+** (poor man's covered calls) or **$10k+** (iron condors).
- **Contract selection**: Automatically pulls Alpaca option chains to target 20-delta weekly calls or 30-day condors; falls back to synthetic OCC symbols when data/APIs are unavailable so telemetry still records intent.
- **Regime-aware gating**: `TradingOrchestrator` invokes theta execution after Gate 6 using the live `RegimeDetector` snapshot, so premium selling only fires in calm/defined-risk regimes.
- **Telemetry**: Every theta plan/execution is recorded under `gate.theta` with opportunity counts, premium gap, and per-leg execution status → the CEO can now see how options are closing the $10/day gap in real time.

---

## 5. Success Criteria

- ✅ Planner JSON + console output present for every trading day.
- ✅ Gap-to-target tracked in dashboard + CEO report.
- ✅ Options accumulation cadence tied to planner-reported deficit.
- 🎯 When planner states `gap_to_target <= 0` for 10 consecutive sessions, we have mathematically demonstrated a sustainable **$10/day** premium engine.

Use this roadmap + tooling loop daily to convert theoretical Rule #1 signals into measurable, auditable income. Once the options planner shows consistent surplus, graduate to the Fibonacci scale-up plan for $30/day → $100/day targets.

---

## 6. Theta Harvest Simulator (NEW)

- `OptionsLiveSimulator` (`src/analytics/options_live_sim.py`) stitches together:
  - Account equity from `data/system_state.json`
  - Latest premium pacing summary from `OptionsProfitPlanner`
  - Theta Harvest plan (equity-gated, IV-aware) from `ThetaHarvestExecutor`
- CLI: `PYTHONPATH=src python3 scripts/run_options_live_sim.py --symbols SPY,QQQ,IWM`
  - Outputs console summary plus `data/options_signals/options_live_sim_latest.json`
  - Flags for `--equity`, `--regime`, and `--dry-run` keep dev/test workflows deterministic.
- This simulator is now the single source of truth for **Month 4 theta ramp readiness**:
  - Shows the daily premium gap vs $10 target *and* how much theta can be deployed immediately.
  - Enables dashboard automation to broadcast “theta on deck” opportunities without manual spreadsheet math.
- Reporting loop: `scripts/report_options_theta.py` writes `data/backtests/options_theta_daily_pl.csv` and `reports/options_theta_strategy.md`, giving you diffable artifacts for CI/backtest review.
