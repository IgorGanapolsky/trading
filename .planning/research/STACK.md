# Stack Research

**Domain:** Automated options trading — exit management and velocity tracking for SPY iron condors
**Researched:** 2026-02-25
**Confidence:** HIGH (broker integration via Context7/official docs; Greeks libs via PyPI + official docs; scheduling via official docs)

---

## Context: What Already Exists

This is a **subsequent milestone** for an existing system. The broker integration layer is already in production:

| Existing Component | File | Status |
|--------------------|------|--------|
| Alpaca broker client | `src/utils/alpaca_client.py` | Production — `alpaca-py==0.43.2` |
| Options risk monitor | `src/risk/options_risk_monitor.py` | Exists — monitors stop-loss/profit by credit math |
| Position manager | `src/risk/position_manager.py` | Exists — equity-centric, options threshold added Feb 24, 2026 |
| Trade recorder | `src/utils/trade_recorder.py` | Exists |
| Performance metrics | `src/utils/performance_metrics.py` | Exists — Sharpe, Sortino, win rate |
| IC position manager | `scripts/manage_iron_condor_positions.py` | Exists — DTE/profit/stop thresholds defined, execution not automated |
| CI scheduling | `.github/workflows/` | Exists — cron-based GitHub Actions |

**The gap:** Exit logic exists but is not continuously monitored and executed. Trade velocity tracking (30-trade gate) and P/L decomposition are missing as automated, live processes.

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `alpaca-py` | `0.43.2` (already pinned) | Greeks retrieval, position monitoring, order execution | Already integrated. `get_option_snapshot()` returns `OptionsSnapshot` with `OptionsGreeks` (delta, gamma, theta, vega, rho) + IV natively — no separate Greeks lib needed for live data. `close_position()` and `MarketOrderRequest` handle all exit order types. |
| `scipy` | `1.16.3` (already pinned) | Black-Scholes IV/Greeks calculation for paper snapshots without live quote | Already in requirements. `scipy.stats.norm` + `scipy.optimize.brentq` is the exact pattern used in Alpaca's own iron condor notebook. Used when real-time option quotes are unavailable (e.g., after hours for position monitoring). |
| `numpy` | `1.26.4` (already pinned) | Vectorized Greeks math, P/L arrays | Already in requirements. Required by scipy and all Greek calculations. |
| `APScheduler` | `3.11.2` | In-process scheduler for market-hours exit monitoring loop | Production-stable (released Dec 22, 2025). Runs inside the existing Python process — no separate service. `BackgroundScheduler` with `IntervalTrigger` runs exit checks every 30 min during market hours without needing a separate scheduler service. Version 4.x is pre-release; do NOT use it. |
| `SQLAlchemy` | `2.0.44` (already pinned) | Trade lifecycle persistence — open/closed IC ledger | Already in requirements. Provides structured queryable trade history for win/loss decomposition, 30-trade gate validation, and P/L attribution. SQLite backend requires no server. Schema: `iron_condor_trade` table with legs, credit_received, DTE_at_entry, exit_reason, closed_pnl. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pandas` | `2.3.3` (already pinned) | Trade DataFrame aggregation, P/L decomposition reports | Computing win rate, profit factor, avg hold time across all closed trades. Required by QuantStats. |
| `quantstats` | `0.0.81` | Portfolio analytics, trade tear sheets, win rate reporting | After 30 closed trades exist. Run `qs.reports.html(returns, output='report.html')` to produce the validation tear sheet for the 30-trade gate. Requires Python >=3.10 — compatible. Do NOT use `pyfolio` (abandoned, pandas compatibility broken). |
| `python-dotenv` | `1.2.1` (already pinned) | Environment variable loading for CI scheduling | Already used. Keeps credentials out of code per data-integrity rules. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| GitHub Actions cron | Scheduled exit monitoring during market hours | Already in use. Add workflow: `*/30 9-16 * * 1-5` UTC-adjusted (14:00-21:00 UTC for EST market hours = `*/30 14-20 * * 1-5`). Minimum GitHub Actions interval is 5 min; 30 min is safe. |
| `ruff` | Linting | Already enforced in CI — all new modules must pass `ruff check src/`. |
| `pytest` | Testing | Already enforced. 30-second timeout required for exit manager tests (avoid network hang). |

---

## Installation

No new packages needed. All required libraries are already in `requirements.txt`. Only code modules need to be written.

```bash
# Verify current versions are correct
pip show alpaca-py scipy numpy sqlalchemy pandas quantstats APScheduler

# If APScheduler is missing (check requirements.txt):
pip install "APScheduler==3.11.2"

# If quantstats is missing:
pip install "quantstats==0.0.81"
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `alpaca-py get_option_snapshot()` for Greeks | `py_vollib_vectorized` (0.1.1, released Feb 2021) | Only if broker data is unavailable. py_vollib_vectorized is faster for batch Greeks on historical backtests but is stale (last release 2021, Python 3.3-3.7 classifiers). For live positions, Alpaca's snapshot endpoint returns verified exchange-sourced Greeks directly — no re-calculation needed. |
| `alpaca-py get_option_snapshot()` for Greeks | `mibian` (0.1.3, released Mar 2016) | Never. Mibian is abandoned — no updates in 10 years, no Python 3 classifiers, no modern packaging. Use `scipy` Black-Scholes (already in requirements) if manual calculation is needed. |
| `APScheduler 3.11.2` | `Celery + Redis` | Only if exit monitoring must scale across multiple processes or machines. For a single-process iron condor system on GitHub Actions, Celery adds a Redis broker dependency with no benefit. |
| `APScheduler 3.11.2` | `APScheduler 4.x` | Never in production. v4.0 is pre-release (4.0.0a6, Apr 2025) with confirmed breaking API changes and no migration path per the maintainer. |
| `SQLAlchemy 2.0.44 + SQLite` | PostgreSQL | Only if multiple writers or remote access are needed. For a single-machine paper trading system, SQLite is sufficient and requires no server. |
| `quantstats 0.0.81` | `pyfolio` | Never. Pyfolio is abandoned by Quantopian. Pandas/NumPy compatibility is broken on modern versions. QuantStats is the maintained successor with equivalent tear-sheet functionality. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `mibian` | Last release 2016, no Python 3 type hints, no maintenance | `scipy.optimize.brentq` + `scipy.stats.norm` for manual Black-Scholes (already in requirements) |
| `py_vollib` / `py_vollib_vectorized` | `py_vollib_vectorized` is stale (Feb 2021); `numba` JIT compilation adds 10-30s cold start which breaks market-hours scheduling | `alpaca-py get_option_snapshot()` returns exchange-sourced Greeks with no calculation overhead |
| `pyfolio` | Abandoned by Quantopian; `pandas` compatibility broken with modern stack | `quantstats 0.0.81` (maintained, Jan 2026 release, Python 3.10+) |
| `APScheduler 4.x` | Pre-release (4.0.0a6), backwards-incompatible API, no migration pathway per maintainer | `APScheduler 3.11.2` |
| Naked options or undefined-risk orders | CLAUDE.md risk-management rule: Phil Town Rule #1 | Iron condors only — always 4-leg defined risk |

---

## Stack Patterns by Variant

**Greeks monitoring for live open positions (market hours):**
- Use `alpaca-py OptionHistoricalDataClient.get_option_snapshot()` with `OptionSnapshotRequest`
- `snapshot.greeks.delta`, `.theta`, `.gamma`, `.vega` — all available natively
- No separate Greeks library needed
- Poll every 30 minutes via APScheduler during 9:30 AM–4:00 PM ET

**Greeks calculation for after-hours/batch validation:**
- Use `scipy` Black-Scholes: `brentq` for IV, `norm.cdf`/`norm.pdf` for delta/gamma/theta/vega
- Pattern already in Alpaca's official iron condor notebook (verified HIGH confidence)
- Already available in requirements — no new install

**Exit order execution:**
- Profit-take (50% of credit): `MarketOrderRequest` via `trade_client.close_position(symbol, ClosePositionRequest(qty="1"))` — one call per leg
- 7 DTE exit: Parse OCC symbol expiry date → compare to `datetime.now()` → `remaining_days <= 7` triggers close
- Stop-loss (200% of credit): Same `close_position` path, triggered by `options_risk_monitor.should_close_position()`

**Trade lifecycle persistence:**
- On entry: write `IronCondorTrade` row (4 leg symbols, credit_received, DTE_at_entry, entry_date)
- On exit: update row (exit_date, exit_price, closed_pnl, exit_reason)
- 30-trade gate: `SELECT COUNT(*) FROM iron_condor_trade WHERE exit_date IS NOT NULL` >= 30

**P/L decomposition:**
- Query closed trades from SQLAlchemy model
- Separate `closed_pnl` by source (iron condor vs cash interest vs other)
- Use `quantstats.stats.win_rate(returns)` after 30+ trades

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `alpaca-py==0.43.2` | `pydantic==2.12.5` | alpaca-py v0.43 requires pydantic v2 — already satisfied |
| `APScheduler==3.11.2` | Python 3.8–3.13 | No conflict with any pinned dependency |
| `quantstats==0.0.81` | Python >=3.10, `pandas>=2.0` | Requires Python 3.10+ and pandas 2.x — both satisfied by existing pinned versions |
| `scipy==1.16.3` | `numpy==1.26.4` | Verified compatible — both already pinned |
| `SQLAlchemy==2.0.44` | Python 3.8+ | Already pinned, no conflict |

---

## Key API Facts (Verified Against Official Docs)

### `OptionsSnapshot` fields (HIGH confidence — official SDK docs)
```python
from alpaca.data.requests import OptionSnapshotRequest
from alpaca.data.historical.option import OptionHistoricalDataClient

client = OptionHistoricalDataClient(api_key, secret_key)
req = OptionSnapshotRequest(symbol_or_symbols=["SPY240920P00540000"])
snapshot = client.get_option_snapshot(req)["SPY240920P00540000"]

# Available fields:
snapshot.greeks.delta    # float
snapshot.greeks.theta    # float
snapshot.greeks.gamma    # float
snapshot.greeks.vega     # float
snapshot.greeks.rho      # float
snapshot.implied_volatility  # float
snapshot.latest_quote.bid_price  # float
snapshot.latest_quote.ask_price  # float
```

### `close_position()` for option exit (HIGH confidence — official SDK docs)
```python
from alpaca.trading.requests import ClosePositionRequest

trade_client.close_position(
    symbol_or_asset_id="SPY240920P00540000",
    close_options=ClosePositionRequest(qty="1")
)
```

### APScheduler market-hours interval (MEDIUM confidence — APScheduler 3.x docs + trading cron patterns)
```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = BackgroundScheduler()
scheduler.add_job(
    check_and_exit_positions,
    CronTrigger(
        day_of_week="mon-fri",
        hour="14-20",       # 9:30 AM - 4:00 PM ET = 14:30-21:00 UTC
        minute="*/30",
        timezone="UTC"
    )
)
scheduler.start()
```

---

## Sources

- `/alpacahq/alpaca-py` (Context7, HIGH) — options snapshot Greeks fields, close_position API, multi-leg order patterns, iron condor notebook Black-Scholes implementation
- https://alpaca.markets/sdks/python/api_reference/data/models.html (official docs, HIGH) — `OptionsGreeks`, `OptionsSnapshot` field list
- https://alpaca.markets/sdks/python/api_reference/data/option/historical.html (official docs, HIGH) — `get_option_snapshot()`, `get_option_chain()` with IV and Greeks
- https://docs.alpaca.markets/docs/real-time-option-data (official docs, HIGH) — WebSocket stream delivers trades/quotes only, NOT Greeks; snapshot polling is the correct approach for Greeks
- https://apscheduler.readthedocs.io/en/3.x/userguide.html (official docs, HIGH) — APScheduler 3.11.2 scheduler types, CronTrigger syntax
- https://pypi.org/project/APScheduler/ (PyPI, HIGH) — v3.11.2 stable (Dec 22, 2025), v4.x is pre-release, do not use
- https://pypi.org/project/quantstats/ (PyPI, HIGH) — v0.0.81 (Jan 13, 2026), Python >=3.10 requirement
- https://pypi.org/project/mibian/ (PyPI, HIGH) — v0.1.3, last updated Mar 2016 — confirmed abandoned
- https://pypi.org/project/py-vollib-vectorized/ (PyPI, HIGH) — v0.1.1, confirmed stale (Feb 2021)
- https://github.com/wilsonfreitas/awesome-quant (WebSearch, MEDIUM) — ecosystem overview for quantitative finance Python libraries

---

*Stack research for: Automated options trading — exit management and velocity tracking*
*Researched: 2026-02-25*
