# Feature Research

**Domain:** Automated Options Trading — Iron Condor Exit Management & Trade Lifecycle
**Researched:** 2026-02-25
**Confidence:** HIGH (based on direct codebase inspection + domain knowledge)

---

## Feature Landscape

### Table Stakes (System Fails Without These)

These are non-negotiable. If missing, the exit management system cannot fulfill its core purpose: completing 30+ trades to validate profitability.

| Feature | Why Expected | Complexity | Current Status | Notes |
|---------|--------------|------------|----------------|-------|
| Automated 50% profit-take exit | Without this, trades stay open indefinitely and capital is tied up | MEDIUM | EXISTS — `manage_iron_condor_positions.py` + `iron-condor-guardian.yml` (30-min schedule) but entry credit data is often missing from `ic_entries.json` | Guardian runs every 30 min but requires entry credit data to compare against; that data is frequently absent |
| Automated 7-DTE time exit | Gamma risk explodes inside 7 DTE; failing to exit = lottery ticket territory | LOW | EXISTS — same scripts parse OCC symbol dates and compute DTE | Working but untested under concurrent 5-IC load |
| Automated 200% stop-loss | Phil Town Rule #1; without hard stops, one bad trade can wipe weeks of premium | LOW | EXISTS — `auto_close_bleeding.py` + guardian enforces 1x credit (100%) stop | Config drift: guardian uses 100%, old scripts use 200% — inconsistent |
| Trade ledger with open/closed state | Cannot compute win rate or P/L without knowing which trades are closed | LOW | EXISTS — `data/ic_trade_log.json` + `data/trades.json` (deprecated dual-source) | Two competing data sources; `trades.json` is flagged deprecated but still used by `calculate_win_rate.py` |
| Win rate tracking (per-trade, decomposed) | CLAUDE.md requires win rate % + avg win + avg loss + profit factor before any scaling decision | LOW | EXISTS — `calculate_win_rate.py` with iron condor filter | Works only when trades are properly logged with `outcome` field |
| Entry credit recording on trade open | All exit rules (50% profit, 200% stop) require knowing what credit was received | LOW | MISSING — `ic_entries.json` often empty; entry credit not automatically saved when iron condor opens | Root cause of exit logic failures: guardian cannot compute P/L without this |
| P/L decomposition (IC vs cash vs interest) | CLAUDE.md mandates `validate_pl_report()` before any P/L claim; prevents false attribution | MEDIUM | EXISTS — `src/utils/pl_validator.py` + `PLReport` dataclass | Not called automatically; requires manual invocation |
| Concurrent position count enforcement | Strategy caps at 5 ICs; exceeding limits violates risk rules | LOW | PARTIAL — `position_enforcer.py` exists; `OptionsExecutor.validate_order()` checks capital, not IC count explicitly | IC count cap needs dedicated check at entry time |
| Market hours gate | Prevents exit orders submitted outside market hours (rejected by broker) | LOW | EXISTS — both workflows check ET market hours before running | Covered |
| Order fill confirmation + retry | Submitted != filled; unconfirmed exits leave positions open | MEDIUM | PARTIAL — `safe_submit_order()` wraps orders; no retry on partial fills | 4-leg IC close can partially fill; no reconciliation logic |

### Differentiators (Competitive Advantage)

Features that accelerate the 30-trade validation goal or improve capital efficiency beyond baseline.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Auto-entry after exit (capital recycling) | When an IC closes at 50% profit in 12 days, immediately open a replacement — compounds velocity from 3 ICs to 5 ICs | HIGH | Not built. Currently the system opens new ICs only during scheduled daily-trading runs, not triggered by exits. This is the primary velocity bottleneck. |
| GRPO-driven dynamic exit threshold | Instead of fixed 50%/200%, ML adjusts exit target based on VIX regime and DTE — e.g., exit at 29% in high-VIX environments (current GRPO optimal: 29%) | HIGH | GRPO learner exists (`grpo_trade_learner.py`) and produces optimal exit %; guardian uses hardcoded 50%. The two are not wired together. |
| Real-time position P/L dashboard | CEO sees current IC P/L, DTE, distance to short strikes without running a script | MEDIUM | Static dashboard exists (`generate_world_class_dashboard_enhanced.py`) but updates only on CI runs, not in real time |
| Per-IC trade attribution | Know precisely which IC generated which P/L — not just total account delta | MEDIUM | `ic_trade_log.json` tracks per-expiry P/L but does not link to entry IDs or GRPO parameters used |
| Expiry cycle diversification enforcement | Force ICs to spread across weekly/monthly expiries to smooth theta income | LOW | Not enforced. Current 3 open ICs all use different expiries but by coincidence, not by policy. |
| XSP/SPX migration for 60/40 tax treatment | Section 1256 contracts save 15-20% on taxes vs SPY (short-term only) at the same risk profile | MEDIUM | `tax_optimization.py` tracks wash sales + PDT; XSP/SPX identified in whitelist (`ALLOWED_TICKERS`) but no migration logic built |
| 30-trade promotion gate (automated check) | CI/CD gate blocks live scaling until 30+ closed ICs with 80%+ win rate — prevents premature scaling | LOW | EXISTS — `generate_strategy_promotion_gate.py` + `enforce_promotion_gate.py` + `check_weekly_cadence_gate.py`. Artifact written to `artifacts/devloop/promotion_gate.json`. |
| GRPO feedback loop from closed trades | Every closed IC feeds its P/L back as verifiable reward into GRPO self-training — the system learns from its own exits | HIGH | `grpo_trade_learner.py` exists but is not called automatically on IC close. Manual `run_grpo_training.py` only. |
| Duplicate exit prevention | Prevent race condition where two guardian runs both try to close the same IC | LOW | EXISTS — `trade_lock.py` + `check_duplicate_execution.py` + workflow concurrency group `global-trade-execution` |

### Anti-Features (Deliberately NOT Build)

| Anti-Feature | Why Requested | Why Problematic | Alternative |
|--------------|---------------|-----------------|-------------|
| Individual stock options exit management | Seems like natural extension | SOFI loss lesson: individual stocks have earnings risk, early assignment, and worse liquidity. SPY/XSP only per CLAUDE.md. | Enforce ticker whitelist on every exit path; reject any non-SPY/XSP position silently |
| Trailing stop exits | Used by stock traders; sounds more sophisticated | For short premium strategies, trailing stops lock in gains prematurely. The premium decays to zero — a fixed % target is more capital-efficient. | Fixed 50% (or GRPO-optimal %) profit target only |
| Naked short option exits | Handling uncovered legs seems like completeness | Naked options have undefined risk — CLAUDE.md prohibits them absolutely. Building exit logic implies we might enter them. | Iron condor only (4-leg, defined risk). Exit logic should reject non-IC positions with explicit error. |
| Real-time tick-by-tick monitoring | Sounds like better coverage | GitHub Actions CI has 5-minute minimum scheduling. Running real-time monitoring requires a persistent server (Cloud Run cost, complexity). The 30-min guardian schedule is sufficient for 30-45 DTE positions. | Keep 30-min guardian schedule; add pre-market and post-market daily summary runs |
| Automated rolling (instead of closing) | "Roll" the untested side for more credit when one side is tested | Rolling decisions require judgment about market direction and credit available. Automating rolling without regime context creates dangerous positions. Phase 1 of the system should close, not roll. | Manual CEO decision for rolls. Automate only clean exits. |
| Multi-leg partial exit (leg-by-leg) | Seems to reduce slippage | Partial IC exits create undefined risk on remaining legs. Closing individual legs without the paired protection removes the defined-risk structure. | Always exit all 4 legs together or not at all |
| P/L projection from fewer than 30 trades | CEO asks "how much will we make?" | `pl_validator.py` rule: NO projections from 0-29 completed trades. This is a hallucination risk. | Report actual closed P/L only. Block projected returns until `can_project == True` in `PLReport`. |

---

## Feature Dependencies

```
[Entry Credit Recording]
    └──required-by──> [50% Profit-Take Exit]
    └──required-by──> [200% Stop-Loss Exit]
    └──required-by──> [Per-IC P/L Attribution]
    └──required-by──> [GRPO Feedback Loop]

[50% Profit-Take Exit]
    └──enables──> [Auto-Entry After Exit] (capital freed = new IC can open)
    └──feeds──> [Win Rate Tracking] (closed trade recorded)
    └──feeds──> [30-Trade Promotion Gate]

[Win Rate Tracking]
    └──required-by──> [30-Trade Promotion Gate]
    └──required-by──> [GRPO Feedback Loop] (reward = win/loss outcome)

[30-Trade Promotion Gate]
    └──blocks──> [Live Account Scaling] (until gate opens)

[GRPO-Driven Dynamic Exit Threshold]
    └──requires──> [GRPO Feedback Loop] (needs completed trade data to train)
    └──enhances──> [50% Profit-Take Exit] (replaces fixed 50% with ML-optimal %)

[XSP/SPX Migration]
    └──requires──> [Entry Credit Recording] (must track basis per instrument for tax lots)
    └──enhances──> [P/L Decomposition] (tax treatment differs by instrument)

[Order Fill Confirmation + Retry]
    └──required-by──> [Auto-Entry After Exit] (must know exit fully filled before opening replacement)
    └──required-by──> [Win Rate Tracking] (cannot record close until fill confirmed)

[Duplicate Exit Prevention]
    └──required-by──> [Auto-Entry After Exit] (prevents double-opening replacements)
```

### Dependency Notes

- **Entry Credit Recording requires trade-open hook:** Every IC entry must write to `ic_entries.json` immediately at order submission, not after fill. Currently this is not wired.
- **Auto-Entry After Exit conflicts with concurrent position cap enforcement:** The cap check must run before opening a replacement to prevent exceeding 5 concurrent ICs.
- **GRPO Feedback Loop depends on Win Rate Tracking:** The reward signal fed to GRPO must use verified closed-trade P/L, not unrealized P/L. This prevents the GRPO from learning from phantom gains.
- **XSP/SPX Migration conflicts with current ticker whitelist:** `ALLOWED_TICKERS` already includes XSP but `options_executor.py` uses SPY-only OCC symbol parsing. Migration requires updating the symbol parser.

---

## MVP Definition

### Launch With (v1) — Close the Exit Management Gap

These are the features preventing the system from completing trades at velocity. Without them, the 30-trade gate cannot be reached.

- [ ] **Entry Credit Recording at trade open** — Wire `iron_condor_trader.py` and `options_executor.py` to write entry credit to `ic_entries.json` immediately on order submission. This unblocks all exit logic.
- [ ] **Dedup `trades.json` vs `ic_trade_log.json`** — Pick one canonical source (recommendation: `ic_trade_log.json` per `data-integrity.md` lessons). Update `calculate_win_rate.py` to read from it. Deprecate `trades.json` for IC tracking.
- [ ] **Stop-loss threshold consistency** — Align `iron_condor_guardian.py` (uses 100% = 1x credit) with `manage_iron_condor_positions.py` (configured at 100% in `IC_EXIT_CONFIG`). Both reference `STOP_LOSS_MULTIPLIER = 1.0`. Currently consistent but the old `auto_close_bleeding.py` uses 50% single-position threshold which is a different concept — document this explicitly.
- [ ] **Order fill confirmation before recording close** — After submitting exit orders for all 4 IC legs, poll until all are filled (or timeout with alert) before writing to trade log. Currently the trade log is updated at submission time, not fill time.
- [ ] **Concurrent IC count gate at entry** — Before opening a new IC, count open iron condors from `ic_entries.json`. Block if count >= 5 (per `CLAUDE.md` strategy rules).

### Add After Validation (v1.x) — Velocity Acceleration

Add once v1 is proving out (10+ closed trades logged correctly):

- [ ] **Auto-entry after exit** — When an IC closes (exit fill confirmed), trigger a new IC opening if market conditions are met (VIX > 20, market hours, count < 5). This converts the 3-IC static position to a continuously cycling book.
- [ ] **GRPO feedback loop on close** — Call `grpo_trade_learner.py` automatically when a trade closes, feeding the outcome as verifiable reward. The GRPO optimal parameters then update for the next entry.
- [ ] **Real-time position P/L in dashboard** — Wire the dashboard generator to read `ic_trade_log.json` live, showing each IC's current P/L % toward the 50% target.

### Future Consideration (v2+) — Tax and Scaling

Defer until 30-trade gate is open and live scaling is approved:

- [ ] **XSP/SPX migration** — Switch from SPY to XSP for 60/40 Section 1256 tax treatment. Requires updating symbol parser, option chain queries, and tax lot tracking. High complexity, high value at scale but zero impact at current $100K paper level.
- [ ] **GRPO-driven dynamic exit threshold** — Replace fixed 50% profit target with GRPO-optimal % that adapts per VIX regime. Currently GRPO optimal is 29%; this would require confidence in the GRPO's training data (needs 30+ trades minimum).
- [ ] **Expiry cycle diversification enforcement** — Formal policy requiring ICs spread across weekly/monthly expiries. Currently ad-hoc.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority | Blocks |
|---------|------------|---------------------|----------|--------|
| Entry credit recording at open | HIGH | LOW | P1 | All exit logic |
| Canonical trade ledger (single source) | HIGH | LOW | P1 | Win rate accuracy |
| Order fill confirmation before log | HIGH | MEDIUM | P1 | Win rate accuracy |
| Concurrent IC count gate | HIGH | LOW | P1 | Risk compliance |
| Stop-loss threshold documentation/consistency | MEDIUM | LOW | P1 | Audit integrity |
| Auto-entry after exit | HIGH | HIGH | P2 | Trade velocity |
| GRPO feedback loop on close | HIGH | MEDIUM | P2 | ML optimization |
| Real-time dashboard P/L | MEDIUM | MEDIUM | P2 | CEO visibility |
| 30-trade promotion gate (already built) | HIGH | LOW | P1 (verify it works) | Live scaling |
| XSP/SPX migration | HIGH (long-term) | HIGH | P3 | Tax optimization |
| GRPO dynamic exit threshold | MEDIUM | HIGH | P3 | Needs 30 trades first |

**Priority key:**
- P1: Must have for v1 — system cannot validate profitability without these
- P2: Should have — accelerates reaching 30-trade gate
- P3: Defer — high complexity, low immediate impact

---

## Competitor Feature Analysis

This is an internal system, not a product competing on the market. The relevant "competitors" are institutional-grade options management platforms. Analysis is directional, not exhaustive.

| Feature | tastytrade (retail platform) | Interactive Brokers (institutional) | This System's Approach |
|---------|-------------------------------|--------------------------------------|------------------------|
| Automated profit-taking | Manual only; alerts + 1-click | Conditional orders (GTC limit to close at target) | Scheduled workflow (30-min); moves toward fill-on-trigger v2 |
| Stop-loss enforcement | Manual; platform stops not available for multi-leg | Complex conditional orders per leg | Auto-close at 1x credit; race-condition protected via trade lock |
| Trade lifecycle tracking | Built-in P/L dashboard per strategy | Flex query API; no built-in strategy grouping | Custom `ic_trade_log.json`; needs single source of truth |
| Win rate analytics | None built-in; third-party tools | None built-in | Custom `calculate_win_rate.py` with 30-trade gate |
| ML-driven parameter optimization | None | None | GRPO learner (unique differentiator) |
| Tax treatment optimization | Section 1256 flagging | Full tax lot tracking | `tax_optimization.py` + XSP migration planned |

---

## Sources

- Codebase inspection: `scripts/iron_condor_guardian.py`, `scripts/manage_iron_condor_positions.py`, `scripts/calculate_win_rate.py`, `scripts/iron_condor_trader.py` (direct code read, HIGH confidence)
- Architecture: `src/safety/auto_close_bleeding.py`, `src/risk/options_risk_monitor.py`, `src/utils/pl_validator.py`, `src/ml/grpo_trade_learner.py` (direct code read, HIGH confidence)
- Project requirements: `.planning/PROJECT.md` (authoritative, HIGH confidence)
- Domain rules: `.claude/CLAUDE.md`, `.claude/rules/trading.md`, `.claude/rules/risk-management.md` (authoritative, HIGH confidence)
- Lessons: LL-268 (7 DTE exit), LL-277 (15-delta IC 86% win rate), LL-281 (auto-close bleeding), LL-230 (data source canonical), LL-220 (15-delta = 86% win rate) — referenced in code comments (MEDIUM confidence — not independently verified from RAG files but consistent across multiple files)
- Gap analysis: `data/ic_entries.json` inspection (empty = missing entry credit recording confirmed), GitHub Actions workflow files (HIGH confidence)

---

*Feature research for: Automated Iron Condor Exit Management System*
*Researched: 2026-02-25*
*Milestone context: Subsequent — What features does an automated exit management system need?*
