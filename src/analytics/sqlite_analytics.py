"""Build a read-only SQLite analytics layer from canonical trading JSON sources."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.core.trading_constants import NORTH_STAR_DAILY_AFTER_TAX, NORTH_STAR_MONTHLY_AFTER_TAX

DEFAULT_DB_OUT = Path("artifacts/devloop/trading_analytics.sqlite")
DEFAULT_SUMMARY_JSON_OUT = Path("artifacts/devloop/sql_analytics_summary.json")
DEFAULT_SUMMARY_MD_OUT = Path("artifacts/devloop/sql_analytics_summary.md")


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _as_float(value: Any, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int | None = None) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on", "pass", "passed"}


def _parse_dt(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _date_part(value: Any) -> str | None:
    parsed = _parse_dt(value)
    if parsed is not None:
        return parsed.date().isoformat()
    if value in (None, ""):
        return None
    raw = str(value).strip()
    return raw[:10] if len(raw) >= 10 else None


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _week_start(value: Any) -> str | None:
    parsed = _parse_dt(value)
    if parsed is None:
        date_str = _date_part(value)
        if not date_str:
            return None
        parsed = _parse_dt(f"{date_str}T00:00:00+00:00")
    if parsed is None:
        return None
    start = parsed.date() - timedelta(days=parsed.date().weekday())
    return start.isoformat()


def _fmt_money(value: Any) -> str:
    numeric = _as_float(value)
    if numeric is None:
        return "n/a"
    return f"${numeric:,.2f}"


def _fmt_pct(value: Any) -> str:
    numeric = _as_float(value)
    if numeric is None:
        return "n/a"
    return f"{numeric:.2f}%"


def _fmt_count(value: Any) -> str:
    numeric = _as_int(value)
    if numeric is None:
        return "n/a"
    return str(numeric)


def _infer_account_type(row: dict[str, Any]) -> str:
    explicit = str(row.get("account_type") or "").strip().lower()
    if explicit in {"paper", "live"}:
        return explicit

    equity = _as_float(row.get("equity"), 0.0) or 0.0
    if equity >= 1_000.0:
        return "paper"
    return "unknown"


def _build_account_daily_rows(repo_root: Path) -> list[dict[str, Any]]:
    data_dir = repo_root / "data"
    performance_log = _read_json(data_dir / "performance_log.json", [])
    verification_reports = _read_json(data_dir / "verification_reports.json", [])
    system_state = _read_json(data_dir / "system_state.json", {})

    merged: dict[str, dict[str, Any]] = {}

    def ensure(date_str: str) -> dict[str, Any]:
        row = merged.setdefault(
            date_str,
            {
                "snapshot_date": date_str,
                "equity": None,
                "cash": None,
                "buying_power": None,
                "daily_pnl": None,
                "total_pnl": None,
                "last_equity": None,
                "traded": None,
                "orders_today": None,
                "structures_today": None,
                "fills_today": None,
                "positions_count": None,
                "captured_at": None,
                "sources": set(),
            },
        )
        return row

    if isinstance(performance_log, list):
        for entry in performance_log:
            if not isinstance(entry, dict):
                continue
            if _infer_account_type(entry) == "live":
                continue
            date_str = _date_part(entry.get("date"))
            if not date_str:
                continue
            row = ensure(date_str)
            row["equity"] = _as_float(entry.get("equity"), row["equity"])
            row["cash"] = _as_float(entry.get("cash"), row["cash"])
            row["buying_power"] = _as_float(entry.get("buying_power"), row["buying_power"])
            row["captured_at"] = entry.get("timestamp") or row["captured_at"]
            row["sources"].add("performance_log")

    if isinstance(verification_reports, list):
        for entry in verification_reports:
            if not isinstance(entry, dict):
                continue
            date_str = _date_part(entry.get("date"))
            if not date_str:
                continue
            row = ensure(date_str)
            row["equity"] = _as_float(entry.get("equity"), row["equity"])
            row["daily_pnl"] = _as_float(entry.get("daily_pnl"), row["daily_pnl"])
            row["total_pnl"] = _as_float(entry.get("total_pnl"), row["total_pnl"])
            row["last_equity"] = _as_float(entry.get("last_equity"), row["last_equity"])
            row["traded"] = _as_bool(entry.get("traded"), row["traded"] or False)
            row["orders_today"] = _as_int(entry.get("orders"), row["orders_today"])
            row["structures_today"] = _as_int(entry.get("structures"), row["structures_today"])
            row["fills_today"] = _as_int(entry.get("fills"), row["fills_today"])
            row["positions_count"] = _as_int(entry.get("positions"), row["positions_count"])
            row["sources"].add("verification_reports")

    if isinstance(system_state, dict):
        paper = (
            system_state.get("paper_account", {})
            if isinstance(system_state.get("paper_account"), dict)
            else {}
        )
        date_str = _date_part(
            system_state.get("meta", {}).get("last_updated")
            if isinstance(system_state.get("meta"), dict)
            else None
        ) or _date_part(system_state.get("last_updated"))
        if date_str:
            row = ensure(date_str)
            row["equity"] = _as_float(
                paper.get("equity") if isinstance(paper, dict) else None,
                row["equity"],
            )
            row["cash"] = _as_float(
                paper.get("cash") if isinstance(paper, dict) else None, row["cash"]
            )
            row["buying_power"] = _as_float(
                paper.get("buying_power") if isinstance(paper, dict) else None,
                row["buying_power"],
            )
            row["daily_pnl"] = _as_float(
                paper.get("daily_change") if isinstance(paper, dict) else None,
                row["daily_pnl"],
            )
            row["total_pnl"] = _as_float(
                paper.get("total_pl") if isinstance(paper, dict) else None,
                row["total_pnl"],
            )
            row["last_equity"] = _as_float(
                paper.get("last_equity") if isinstance(paper, dict) else None,
                row["last_equity"],
            )
            row["positions_count"] = _as_int(
                paper.get("positions_count") if isinstance(paper, dict) else None,
                row["positions_count"],
            )
            row["captured_at"] = (
                (
                    system_state.get("meta", {}).get("last_updated")
                    if isinstance(system_state.get("meta"), dict)
                    else None
                )
                or system_state.get("last_updated")
                or row["captured_at"]
            )
            row["sources"].add("system_state")

    rows: list[dict[str, Any]] = []
    for date_str in sorted(merged):
        row = merged[date_str]
        if row["equity"] is None:
            continue
        rows.append(
            {
                **row,
                "sources": ",".join(sorted(row["sources"])),
            }
        )
    return rows


def _build_closed_trade_rows(repo_root: Path) -> list[dict[str, Any]]:
    ledger = _read_json(repo_root / "data" / "trades.json", {})
    trades = ledger.get("trades", []) if isinstance(ledger, dict) else []
    if not isinstance(trades, list):
        return []

    rows: list[dict[str, Any]] = []
    for trade in trades:
        if not isinstance(trade, dict):
            continue
        if str(trade.get("status") or "").lower() != "closed":
            continue
        rows.append(
            {
                "trade_id": str(trade.get("id") or ""),
                "symbol": str(trade.get("symbol") or ""),
                "strategy": str(trade.get("strategy") or ""),
                "entry_date": _date_part(trade.get("entry_date")),
                "exit_date": _date_part(trade.get("exit_date")),
                "realized_pnl": _as_float(trade.get("realized_pnl"), 0.0) or 0.0,
                "outcome": str(trade.get("outcome") or ""),
                "source": str(trade.get("source") or ""),
            }
        )
    rows.sort(key=lambda row: ((row.get("exit_date") or ""), row["trade_id"]))
    return rows


def _build_north_star_weekly_rows(repo_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    data_dir = repo_root / "data"
    history = _read_json(data_dir / "north_star_weekly_history.json", [])
    system_state = _read_json(data_dir / "system_state.json", {})

    deduped: dict[str, dict[str, Any]] = {}
    if isinstance(history, list):
        for entry in history:
            if not isinstance(entry, dict):
                continue
            week_start = _date_part(entry.get("week_start"))
            if not week_start:
                continue
            deduped[week_start] = {
                "week_start": week_start,
                "updated_at": entry.get("updated_at"),
                "sample_size": _as_int(entry.get("sample_size"), 0) or 0,
                "win_rate_pct": _as_float(entry.get("win_rate_pct"), 0.0) or 0.0,
                "expectancy_per_trade": _as_float(entry.get("expectancy_per_trade"), 0.0) or 0.0,
                "mode": str(entry.get("mode") or "unknown"),
                "qualified_setups": _as_int(entry.get("qualified_setups"), 0) or 0,
                "cadence_passed": _as_bool(entry.get("cadence_passed"), False),
                "source": "north_star_weekly_history",
            }

    gate = (
        system_state.get("north_star_weekly_gate", {})
        if isinstance(system_state.get("north_star_weekly_gate"), dict)
        else {}
    )
    cadence = gate.get("cadence_kpi", {}) if isinstance(gate.get("cadence_kpi"), dict) else {}
    gate_updated = gate.get("updated_at")
    gate_week = _week_start(gate_updated)
    if gate_week:
        deduped[gate_week] = {
            "week_start": gate_week,
            "updated_at": gate_updated,
            "sample_size": _as_int(gate.get("sample_size"), 0) or 0,
            "win_rate_pct": _as_float(gate.get("win_rate_pct"), 0.0) or 0.0,
            "expectancy_per_trade": _as_float(gate.get("expectancy_per_trade"), 0.0) or 0.0,
            "mode": str(gate.get("mode") or "unknown"),
            "qualified_setups": _as_int(cadence.get("qualified_setups_observed"), 0) or 0,
            "cadence_passed": _as_bool(cadence.get("passed"), False),
            "source": "system_state.north_star_weekly_gate",
        }

    north_star = (
        system_state.get("north_star", {})
        if isinstance(system_state.get("north_star"), dict)
        else {}
    )
    state_row = {
        "monthly_after_tax_target": _as_float(
            north_star.get("monthly_after_tax_target"),
            NORTH_STAR_MONTHLY_AFTER_TAX,
        )
        or NORTH_STAR_MONTHLY_AFTER_TAX,
        "daily_after_tax_target": _as_float(
            north_star.get("daily_after_tax_target"),
            NORTH_STAR_DAILY_AFTER_TAX,
        )
        or NORTH_STAR_DAILY_AFTER_TAX,
        "probability_score": _as_float(north_star.get("probability_score")),
        "probability_label": str(north_star.get("probability_label") or "unknown"),
        "monthly_target_progress_pct": _as_float(north_star.get("monthly_target_progress_pct")),
        "estimated_monthly_after_tax_from_expectancy": _as_float(
            north_star.get("estimated_monthly_after_tax_from_expectancy")
        ),
        "target_capital": _as_float(north_star.get("target_capital")),
        "target_date": north_star.get("target_date"),
        "updated_at": north_star.get("updated_at") or gate_updated,
    }

    rows = [deduped[key] for key in sorted(deduped)]
    return rows, state_row


def _initialise_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA foreign_keys = OFF;
        DROP VIEW IF EXISTS north_star_progress;
        DROP VIEW IF EXISTS closed_trades_pop;
        DROP VIEW IF EXISTS account_daily_pop;
        DROP TABLE IF EXISTS north_star_state;
        DROP TABLE IF EXISTS north_star_weekly;
        DROP TABLE IF EXISTS closed_trades;
        DROP TABLE IF EXISTS account_daily_snapshots;

        CREATE TABLE account_daily_snapshots (
            snapshot_date TEXT PRIMARY KEY,
            equity REAL,
            cash REAL,
            buying_power REAL,
            daily_pnl REAL,
            total_pnl REAL,
            last_equity REAL,
            traded INTEGER,
            orders_today INTEGER,
            structures_today INTEGER,
            fills_today INTEGER,
            positions_count INTEGER,
            captured_at TEXT,
            sources TEXT NOT NULL
        );

        CREATE TABLE closed_trades (
            trade_id TEXT PRIMARY KEY,
            symbol TEXT,
            strategy TEXT,
            entry_date TEXT,
            exit_date TEXT,
            realized_pnl REAL NOT NULL,
            outcome TEXT,
            source TEXT
        );

        CREATE TABLE north_star_weekly (
            week_start TEXT PRIMARY KEY,
            updated_at TEXT,
            sample_size INTEGER NOT NULL,
            win_rate_pct REAL NOT NULL,
            expectancy_per_trade REAL NOT NULL,
            mode TEXT,
            qualified_setups INTEGER NOT NULL,
            cadence_passed INTEGER NOT NULL,
            source TEXT
        );

        CREATE TABLE north_star_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            monthly_after_tax_target REAL NOT NULL,
            daily_after_tax_target REAL NOT NULL,
            probability_score REAL,
            probability_label TEXT,
            monthly_target_progress_pct REAL,
            estimated_monthly_after_tax_from_expectancy REAL,
            target_capital REAL,
            target_date TEXT,
            updated_at TEXT
        );

        CREATE VIEW account_daily_pop AS
        WITH base AS (
            SELECT
                snapshot_date,
                equity,
                cash,
                buying_power,
                daily_pnl,
                total_pnl,
                last_equity,
                traded,
                orders_today,
                structures_today,
                fills_today,
                positions_count,
                captured_at,
                sources,
                LAG(equity) OVER (ORDER BY snapshot_date) AS prev_equity,
                LAG(COALESCE(daily_pnl, 0.0)) OVER (ORDER BY snapshot_date) AS prev_daily_pnl
            FROM account_daily_snapshots
        )
        SELECT
            snapshot_date,
            equity,
            cash,
            buying_power,
            COALESCE(daily_pnl, ROUND(equity - prev_equity, 2)) AS resolved_daily_pnl,
            total_pnl,
            last_equity,
            traded,
            orders_today,
            structures_today,
            fills_today,
            positions_count,
            captured_at,
            sources,
            prev_equity,
            ROUND(equity - prev_equity, 2) AS equity_change_vs_prev_snapshot,
            ROUND(
                CASE
                    WHEN prev_equity IS NULL OR prev_equity = 0 THEN NULL
                    ELSE ((equity / prev_equity) - 1.0) * 100.0
                END,
                4
            ) AS equity_change_pct_vs_prev_snapshot,
            prev_daily_pnl,
            ROUND(COALESCE(daily_pnl, equity - prev_equity) - prev_daily_pnl, 2) AS daily_pnl_delta_vs_prev_snapshot,
            ROUND(
                SUM(COALESCE(daily_pnl, equity - prev_equity))
                OVER (ORDER BY snapshot_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW),
                2
            ) AS rolling_5d_pnl
        FROM base
        ORDER BY snapshot_date;

        CREATE VIEW closed_trades_pop AS
        WITH daily AS (
            SELECT
                exit_date AS trade_date,
                COUNT(*) AS closed_trades,
                ROUND(SUM(realized_pnl), 2) AS realized_pnl,
                ROUND(AVG(realized_pnl), 2) AS expectancy_per_trade,
                SUM(CASE WHEN LOWER(outcome) = 'win' THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN LOWER(outcome) = 'loss' THEN 1 ELSE 0 END) AS losses
            FROM closed_trades
            WHERE exit_date IS NOT NULL
            GROUP BY exit_date
        )
        SELECT
            trade_date,
            closed_trades,
            realized_pnl,
            expectancy_per_trade,
            wins,
            losses,
            LAG(realized_pnl) OVER (ORDER BY trade_date) AS prev_realized_pnl,
            ROUND(realized_pnl - LAG(realized_pnl) OVER (ORDER BY trade_date), 2) AS realized_pnl_delta,
            LAG(expectancy_per_trade) OVER (ORDER BY trade_date) AS prev_expectancy_per_trade,
            ROUND(expectancy_per_trade - LAG(expectancy_per_trade) OVER (ORDER BY trade_date), 2) AS expectancy_delta,
            ROUND(
                SUM(realized_pnl) OVER (ORDER BY trade_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW),
                2
            ) AS cumulative_realized_pnl
        FROM daily
        ORDER BY trade_date;

        CREATE VIEW north_star_progress AS
        SELECT
            w.week_start,
            w.updated_at,
            w.sample_size,
            w.win_rate_pct,
            w.expectancy_per_trade,
            w.mode,
            w.qualified_setups,
            w.cadence_passed,
            w.source,
            s.monthly_after_tax_target,
            s.daily_after_tax_target,
            s.probability_score,
            s.probability_label,
            s.monthly_target_progress_pct,
            s.estimated_monthly_after_tax_from_expectancy,
            s.target_capital,
            s.target_date,
            LAG(w.expectancy_per_trade) OVER (ORDER BY w.week_start) AS prev_expectancy_per_trade,
            ROUND(w.expectancy_per_trade - LAG(w.expectancy_per_trade) OVER (ORDER BY w.week_start), 2) AS expectancy_delta,
            LAG(w.win_rate_pct) OVER (ORDER BY w.week_start) AS prev_win_rate_pct,
            ROUND(w.win_rate_pct - LAG(w.win_rate_pct) OVER (ORDER BY w.week_start), 2) AS win_rate_delta_pct
        FROM north_star_weekly w
        CROSS JOIN north_star_state s
        ORDER BY w.week_start;
        """
    )


def _insert_rows(
    conn: sqlite3.Connection,
    account_rows: list[dict[str, Any]],
    closed_trade_rows: list[dict[str, Any]],
    north_star_weekly_rows: list[dict[str, Any]],
    north_star_state_row: dict[str, Any],
) -> None:
    conn.executemany(
        """
        INSERT INTO account_daily_snapshots (
            snapshot_date,
            equity,
            cash,
            buying_power,
            daily_pnl,
            total_pnl,
            last_equity,
            traded,
            orders_today,
            structures_today,
            fills_today,
            positions_count,
            captured_at,
            sources
        ) VALUES (
            :snapshot_date,
            :equity,
            :cash,
            :buying_power,
            :daily_pnl,
            :total_pnl,
            :last_equity,
            :traded,
            :orders_today,
            :structures_today,
            :fills_today,
            :positions_count,
            :captured_at,
            :sources
        )
        """,
        [
            {
                **row,
                "traded": int(_as_bool(row.get("traded"), False))
                if row.get("traded") is not None
                else None,
            }
            for row in account_rows
        ],
    )

    conn.executemany(
        """
        INSERT INTO closed_trades (
            trade_id,
            symbol,
            strategy,
            entry_date,
            exit_date,
            realized_pnl,
            outcome,
            source
        ) VALUES (
            :trade_id,
            :symbol,
            :strategy,
            :entry_date,
            :exit_date,
            :realized_pnl,
            :outcome,
            :source
        )
        """,
        closed_trade_rows,
    )

    conn.executemany(
        """
        INSERT INTO north_star_weekly (
            week_start,
            updated_at,
            sample_size,
            win_rate_pct,
            expectancy_per_trade,
            mode,
            qualified_setups,
            cadence_passed,
            source
        ) VALUES (
            :week_start,
            :updated_at,
            :sample_size,
            :win_rate_pct,
            :expectancy_per_trade,
            :mode,
            :qualified_setups,
            :cadence_passed,
            :source
        )
        """,
        [
            {
                **row,
                "cadence_passed": int(_as_bool(row.get("cadence_passed"), False)),
            }
            for row in north_star_weekly_rows
        ],
    )

    conn.execute(
        """
        INSERT INTO north_star_state (
            id,
            monthly_after_tax_target,
            daily_after_tax_target,
            probability_score,
            probability_label,
            monthly_target_progress_pct,
            estimated_monthly_after_tax_from_expectancy,
            target_capital,
            target_date,
            updated_at
        ) VALUES (
            1,
            :monthly_after_tax_target,
            :daily_after_tax_target,
            :probability_score,
            :probability_label,
            :monthly_target_progress_pct,
            :estimated_monthly_after_tax_from_expectancy,
            :target_capital,
            :target_date,
            :updated_at
        )
        """,
        north_star_state_row,
    )

    conn.commit()


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def _build_highlights(
    account_row: dict[str, Any] | None,
    closed_trade_row: dict[str, Any] | None,
    north_star_row: dict[str, Any] | None,
    *,
    closed_trade_count: int,
) -> list[str]:
    highlights: list[str] = []

    if account_row:
        equity_delta = _as_float(account_row.get("equity_change_vs_prev_snapshot"))
        if equity_delta is None:
            highlights.append(
                f"Latest equity snapshot is {_fmt_money(account_row.get('equity'))}; no prior snapshot yet for PoP comparison."
            )
        elif equity_delta > 0:
            highlights.append(
                f"Equity improved by {_fmt_money(equity_delta)} versus the previous snapshot, with resolved daily P/L {_fmt_money(account_row.get('resolved_daily_pnl'))}."
            )
        elif equity_delta < 0:
            highlights.append(
                f"Equity declined by {_fmt_money(abs(equity_delta))} versus the previous snapshot, with resolved daily P/L {_fmt_money(account_row.get('resolved_daily_pnl'))}."
            )
        else:
            highlights.append(
                f"Equity was flat versus the previous snapshot at {_fmt_money(account_row.get('equity'))}."
            )

    if closed_trade_row:
        highlights.append(
            f"Closed-trade ledger now contains {closed_trade_count} closed trade(s); latest realized P/L was {_fmt_money(closed_trade_row.get('realized_pnl'))} on {closed_trade_row.get('trade_date')}."
        )
    else:
        highlights.append(
            "Closed-trade ledger does not yet have any completed trades for expectancy analysis."
        )

    if north_star_row:
        cadence_passed = _as_bool(north_star_row.get("cadence_passed"), False)
        probability_label = str(north_star_row.get("probability_label") or "unknown").upper()
        highlights.append(
            "North Star weekly gate is "
            + ("passing" if cadence_passed else "blocked")
            + f"; probability label is {probability_label} and monthly target remains {_fmt_money(north_star_row.get('monthly_after_tax_target'))}."
        )

    return highlights


def _build_summary(
    conn: sqlite3.Connection,
    *,
    repo_root: Path,
    db_path: Path,
    account_rows: list[dict[str, Any]],
    closed_trade_rows: list[dict[str, Any]],
    north_star_weekly_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    conn.row_factory = sqlite3.Row
    account_row = _row_to_dict(
        conn.execute(
            "SELECT * FROM account_daily_pop ORDER BY snapshot_date DESC LIMIT 1"
        ).fetchone()
    )
    closed_trade_row = _row_to_dict(
        conn.execute("SELECT * FROM closed_trades_pop ORDER BY trade_date DESC LIMIT 1").fetchone()
    )
    north_star_row = _row_to_dict(
        conn.execute(
            "SELECT * FROM north_star_progress ORDER BY week_start DESC LIMIT 1"
        ).fetchone()
    )

    summary = {
        "generated_at_utc": _iso_now(),
        "repo_root": str(repo_root),
        "db_path": str(db_path),
        "sources": {
            "account_daily_snapshots": len(account_rows),
            "closed_trades": len(closed_trade_rows),
            "north_star_weekly_rows": len(north_star_weekly_rows),
            "system_state_present": (repo_root / "data" / "system_state.json").exists(),
            "performance_log_present": (repo_root / "data" / "performance_log.json").exists(),
            "verification_reports_present": (
                repo_root / "data" / "verification_reports.json"
            ).exists(),
            "trades_ledger_present": (repo_root / "data" / "trades.json").exists(),
        },
        "account_daily_pop": account_row,
        "closed_trade_pop": closed_trade_row,
        "north_star_progress": north_star_row,
        "highlights": _build_highlights(
            account_row,
            closed_trade_row,
            north_star_row,
            closed_trade_count=len(closed_trade_rows),
        ),
    }
    return summary


def render_sql_analytics_summary(summary: dict[str, Any]) -> str:
    account = summary.get("account_daily_pop") or {}
    closed_trade = summary.get("closed_trade_pop") or {}
    north_star = summary.get("north_star_progress") or {}
    sources = summary.get("sources") or {}
    highlights = summary.get("highlights") or []

    lines = [
        "# SQL Analytics Summary",
        "",
        f"- Generated at: `{summary.get('generated_at_utc')}`",
        f"- SQLite DB: `{summary.get('db_path')}`",
        "",
        "## Source Coverage",
        f"- Account snapshots loaded: `{sources.get('account_daily_snapshots')}`",
        f"- Closed trades loaded: `{sources.get('closed_trades')}`",
        f"- Weekly North Star rows loaded: `{sources.get('north_star_weekly_rows')}`",
        "",
        "## Account Daily PoP",
        f"- Snapshot date: `{account.get('snapshot_date', 'n/a')}`",
        f"- Equity: `{_fmt_money(account.get('equity'))}`",
        f"- Resolved daily P/L: `{_fmt_money(account.get('resolved_daily_pnl'))}`",
        f"- Prior equity: `{_fmt_money(account.get('prev_equity'))}`",
        f"- Equity change vs prior snapshot: `{_fmt_money(account.get('equity_change_vs_prev_snapshot'))}`",
        f"- Equity change % vs prior snapshot: `{_fmt_pct(account.get('equity_change_pct_vs_prev_snapshot'))}`",
        f"- Rolling 5D P/L: `{_fmt_money(account.get('rolling_5d_pnl'))}`",
        f"- Trade activity: orders `{_fmt_count(account.get('orders_today'))}`, structures `{_fmt_count(account.get('structures_today'))}`, fills `{_fmt_count(account.get('fills_today'))}`",
        "",
        "## Closed Trade PoP",
        f"- Trade date: `{closed_trade.get('trade_date', 'n/a')}`",
        f"- Closed trades on date: `{_fmt_count(closed_trade.get('closed_trades'))}`",
        f"- Realized P/L: `{_fmt_money(closed_trade.get('realized_pnl'))}`",
        f"- Realized P/L delta: `{_fmt_money(closed_trade.get('realized_pnl_delta'))}`",
        f"- Expectancy per trade: `{_fmt_money(closed_trade.get('expectancy_per_trade'))}`",
        f"- Cumulative realized P/L: `{_fmt_money(closed_trade.get('cumulative_realized_pnl'))}`",
        "",
        "## North Star Weekly PoP",
        f"- Week start: `{north_star.get('week_start', 'n/a')}`",
        f"- Monthly target: `{_fmt_money(north_star.get('monthly_after_tax_target'))}`",
        f"- Probability: `{_fmt_pct(north_star.get('probability_score'))}` (`{north_star.get('probability_label', 'unknown')}`)",
        f"- Monthly progress: `{_fmt_pct(north_star.get('monthly_target_progress_pct'))}`",
        f"- Expectancy per trade: `{_fmt_money(north_star.get('expectancy_per_trade'))}`",
        f"- Expectancy delta vs prior week: `{_fmt_money(north_star.get('expectancy_delta'))}`",
        f"- Weekly win rate: `{_fmt_pct(north_star.get('win_rate_pct'))}`",
        f"- Weekly cadence passed: `{_as_bool(north_star.get('cadence_passed'), False)}`",
        "",
        "## Highlights",
    ]
    lines.extend([f"- {item}" for item in highlights] or ["- No highlights generated."])
    lines.append("")
    return "\n".join(lines)


def build_analytics_artifacts(
    repo_root: Path,
    *,
    db_path: Path = DEFAULT_DB_OUT,
    summary_json_path: Path = DEFAULT_SUMMARY_JSON_OUT,
    summary_md_path: Path = DEFAULT_SUMMARY_MD_OUT,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    db_path = db_path if db_path.is_absolute() else repo_root / db_path
    summary_json_path = (
        summary_json_path if summary_json_path.is_absolute() else repo_root / summary_json_path
    )
    summary_md_path = (
        summary_md_path if summary_md_path.is_absolute() else repo_root / summary_md_path
    )

    account_rows = _build_account_daily_rows(repo_root)
    closed_trade_rows = _build_closed_trade_rows(repo_root)
    north_star_weekly_rows, north_star_state_row = _build_north_star_weekly_rows(repo_root)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    summary_json_path.parent.mkdir(parents=True, exist_ok=True)
    summary_md_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    with sqlite3.connect(db_path) as conn:
        _initialise_schema(conn)
        _insert_rows(
            conn,
            account_rows=account_rows,
            closed_trade_rows=closed_trade_rows,
            north_star_weekly_rows=north_star_weekly_rows,
            north_star_state_row=north_star_state_row,
        )
        summary = _build_summary(
            conn,
            repo_root=repo_root,
            db_path=db_path,
            account_rows=account_rows,
            closed_trade_rows=closed_trade_rows,
            north_star_weekly_rows=north_star_weekly_rows,
        )

    summary_json_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    summary_md_path.write_text(render_sql_analytics_summary(summary), encoding="utf-8")
    return summary
