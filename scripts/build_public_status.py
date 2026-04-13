#!/usr/bin/env python3
"""Build canonical public-status artifacts for docs and wiki surfaces."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.safety.north_star_congruence import assess_gate_congruence  # noqa: E402


def _load_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(default or {})


def _fmt_money(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "n/a"


def _fmt_pct(value: Any) -> str:
    try:
        return f"{float(value):.2f}%"
    except (TypeError, ValueError):
        return "n/a"


def _short_status(block_new_positions: bool | None, mode: str | None) -> str:
    """Determine public-facing status.

    During validation_reset, show mode even if congruence flags contradiction.
    The contradiction is expected — lifetime ledger is negative from old trades
    while validation is proving new edge.
    """
    normalized_mode = str(mode).lower() if mode else None
    if normalized_mode == "validation_reset":
        return normalized_mode
    if block_new_positions:
        return "halted"
    if normalized_mode:
        return normalized_mode
    return "unknown"


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on", "pass", "passed"}:
            return True
        if normalized in {"false", "0", "no", "n", "off", "fail", "failed"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def _weekly_claims_readiness(weekly: dict[str, Any]) -> bool:
    mode = str(weekly.get("mode") or "unknown").lower()
    validation_reset_active = bool(
        mode == "validation_reset"
        and _as_bool(weekly.get("allow_validation_entries"))
        and _as_bool(weekly.get("block_live_new_positions"))
    )
    return bool(
        _as_bool(weekly.get("verified_edge_available"))
        or (
            "block_new_positions" in weekly
            and not _as_bool(weekly.get("block_new_positions"))
            and not validation_reset_active
        )
        or mode == "expansion_candidate"
    )


def _public_fail_closed(weekly: dict[str, Any], congruence: dict[str, Any]) -> bool:
    if _as_bool(weekly.get("block_new_positions")):
        return True
    if bool(congruence["contradiction_detected"]):
        return True
    return bool(
        _weekly_claims_readiness(weekly)
        and not bool(congruence["lifetime_ledger"]["edge_confirmed"])
    )


def _blocker_reason(weekly: dict[str, Any], congruence: dict[str, Any]) -> Any:
    if congruence["contradiction_reason"]:
        return congruence["contradiction_reason"]
    if (
        _weekly_claims_readiness(weekly)
        and not bool(congruence["lifetime_ledger"]["edge_confirmed"])
    ):
        return (
            "CRITICAL: Weekly gate claims readiness before the lifetime paired-trade "
            "ledger has confirmed positive edge. Block new positions until lifetime "
            "expectancy and profit factor are positive."
        )
    return weekly.get("reason")


def _pick_first(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _why_today_summary(total: Any, positions_count: Any) -> str:
    if total is not None and positions_count == 0:
        return (
            f"Latest tracked broker sync shows {_fmt_money(total)} today with no open paper positions. "
            "Use the operator scorecard for fill-level decomposition."
        )
    if total is not None and positions_count is not None:
        return (
            f"Latest tracked broker sync shows {_fmt_money(total)} today with {positions_count} open paper positions. "
            "Use the operator scorecard for realized/unrealized and leg-level decomposition."
        )
    if total is not None:
        return (
            f"Latest tracked broker sync shows {_fmt_money(total)} today. "
            "Use the operator scorecard for realized/unrealized and fill-level decomposition."
        )
    return "Latest daily scorecard is unavailable."


def build_public_status(repo_root: Path) -> dict[str, Any]:
    runtime = _load_json(repo_root / "data/runtime/intraday_pnl_latest.json")
    state = _load_json(repo_root / "data/system_state.json")
    trades = _load_json(repo_root / "data/trades.json")
    scorecard = _load_json(repo_root / "artifacts/daily_scorecard/latest_daily_scorecard.json")

    runtime_paper = runtime.get("paper", {})
    runtime_live = runtime.get("live", {})
    weekly = state.get("north_star_weekly_gate") or {}
    cadence = weekly.get("cadence_kpi") or {}
    scaling = weekly.get("scaling_sample_gate") or {}
    stats = trades.get("stats") or {}
    congruence = assess_gate_congruence(weekly, trades)
    paper_total_pnl_today = _pick_first(
        runtime_paper.get("daily_change"),
        scorecard.get("paper", {}).get("total_pnl_today"),
    )
    generated_at_et = _pick_first(
        runtime.get("captured_at"),
        state.get("last_updated"),
        stats.get("last_updated"),
        trades.get("meta", {}).get("last_sync"),
        scorecard.get("generated_at_et"),
        datetime.now().astimezone().isoformat(),
    )

    closed_total = stats.get("closed_trades", scaling.get("closed_trades_observed", 0))
    total_realized = stats.get("total_realized_pnl", stats.get("total_pnl"))
    fail_closed = _public_fail_closed(weekly, congruence)
    blocker_reason = _blocker_reason(weekly, congruence)

    return {
        "generated_at_et": generated_at_et,
        "system": {
            "name": "SPY Options Validation Platform",
            "tagline": "Broker-backed scorecards, hard risk gates, paired-trade accounting, and live operator surfaces.",
            "public_status": _short_status(
                fail_closed,
                weekly.get("mode"),
            ),
        },
        "paper": {
            "equity": _pick_first(
                runtime_paper.get("equity"),
                scorecard.get("paper", {}).get("equity"),
            ),
            "total_pnl_today": paper_total_pnl_today,
            "realized_pnl_today": None,
            "unrealized_pnl_today": None,
            "fills_today_count": None,
            "positions_count": runtime_paper.get("positions_count"),
        },
        "live": {
            "equity": _pick_first(
                runtime_live.get("equity"), scorecard.get("live", {}).get("equity")
            ),
            "total_pnl_today": _pick_first(
                runtime_live.get("daily_change"),
                scorecard.get("live", {}).get("total_pnl_today"),
            ),
        },
        "ledger": {
            "closed_trades_total": closed_total,
            "wins": stats.get("wins"),
            "losses": stats.get("losses"),
            "breakeven": stats.get("breakeven"),
            "win_rate_pct": stats.get("win_rate_pct"),
            "profit_factor": stats.get("profit_factor"),
            "total_realized_pnl": total_realized,
            "expectancy_per_trade": congruence["lifetime_ledger"]["expectancy_per_trade"],
            "last_updated": stats.get("last_updated") or trades.get("meta", {}).get("last_sync"),
        },
        "gate": {
            "mode": weekly.get("mode"),
            "block_new_positions": fail_closed,
            "verified_edge_available": congruence["effective_verified_edge_available"],
            "recommended_max_position_pct": weekly.get("recommended_max_position_pct"),
            "sample_size": weekly.get("sample_size"),
            "expectancy_per_trade": weekly.get("expectancy_per_trade"),
            "win_rate_pct": weekly.get("win_rate_pct"),
            "blocker_reason": blocker_reason,
            "qualified_setups_this_week": cadence.get("qualified_setups_observed"),
            "closed_trades_this_week": cadence.get("closed_trades_observed"),
            "scale_allowed": congruence["effective_scale_allowed"],
            "scaling_gate_closed_trades_observed": scaling.get(
                "closed_trades_observed", closed_total
            ),
            "scaling_gate_min_closed_trades": scaling.get("min_closed_trades_for_scaling"),
            "contradiction_detected": congruence["contradiction_detected"],
            "lifetime_edge_confirmed": congruence["lifetime_ledger"]["edge_confirmed"],
            "lifetime_closed_trades": congruence["lifetime_ledger"]["closed_trades"],
            "lifetime_profit_factor": congruence["lifetime_ledger"]["profit_factor"],
            "lifetime_expectancy_per_trade": congruence["lifetime_ledger"]["expectancy_per_trade"],
            "lifetime_total_realized_pnl": congruence["lifetime_ledger"]["total_realized_pnl"],
        },
        "narrative": {
            "summary": _why_today_summary(
                paper_total_pnl_today,
                runtime_paper.get("positions_count"),
            ),
            "thesis": (
                "This project is currently a paper-first validation platform, not a proven passive-income engine. "
                "Public surfaces should show current gate state and broker-backed evidence rather than frozen claims."
            ),
        },
        "links": {
            "operator_dashboard": "https://github.com/IgorGanapolsky/trading/wiki/Progress-Dashboard",
            "repo": "https://github.com/IgorGanapolsky/trading",
            "wiki": "https://github.com/IgorGanapolsky/trading/wiki",
        },
    }


def render_progress_dashboard(status: dict[str, Any]) -> str:
    gate = status["gate"]
    paper = status["paper"]
    ledger = status["ledger"]
    return "\n".join(
        [
            "# Progress Dashboard",
            "",
            f"Generated from canonical ledgers at `{status['generated_at_et']}`.",
            "",
            "This page is generated from broker-backed scorecards and the canonical paired-trade ledger. "
            "If this page and the public dashboard diverge, the generated dashboard is the source of truth.",
            "",
            "## Current Status",
            "",
            f"- Paper equity: `{_fmt_money(paper.get('equity'))}`",
            f"- Paper total P/L today: `{_fmt_money(paper.get('total_pnl_today'))}`",
            f"- Paper realized P/L today: `{_fmt_money(paper.get('realized_pnl_today'))}`",
            f"- Paper unrealized P/L today: `{_fmt_money(paper.get('unrealized_pnl_today'))}`",
            f"- Fills today: `{paper.get('fills_today_count', 0)}`",
            f"- Closed trades total: `{ledger.get('closed_trades_total', 0)}`",
            f"- Total realized P/L: `{_fmt_money(ledger.get('total_realized_pnl'))}`",
            f"- Win rate: `{_fmt_pct(ledger.get('win_rate_pct'))}`",
            f"- Profit factor: `{ledger.get('profit_factor', 'n/a')}`",
            "",
            "## Gate State",
            "",
            f"- Mode: `{gate.get('mode', 'unknown')}`",
            f"- Block new positions: `{gate.get('block_new_positions')}`",
            f"- Verified edge available: `{gate.get('verified_edge_available')}`",
            f"- Recommended max position size: `{gate.get('recommended_max_position_pct')}`",
            f"- Weekly expectancy per trade: `{_fmt_money(gate.get('expectancy_per_trade'))}`",
            f"- Scaling gate: `{gate.get('scaling_gate_closed_trades_observed')}` / `{gate.get('scaling_gate_min_closed_trades')}`",
            f"- Qualified setups this week: `{gate.get('qualified_setups_this_week')}`",
            f"- Closed trades this week: `{gate.get('closed_trades_this_week')}`",
            "",
            "## Exact Blocker",
            "",
            f"`{gate.get('blocker_reason', 'n/a')}`",
            "",
            "## Canonical Links",
            "",
            "- Public dashboard: https://igorganapolsky.github.io/trading/rag-query.html",
            f"- GitHub repo: {status['links']['repo']}",
            f"- Wiki: {status['links']['wiki']}",
        ]
    )


def render_home(status: dict[str, Any]) -> str:
    gate = status["gate"]
    ledger = status["ledger"]
    return "\n".join(
        [
            "# SPY Options Validation Platform Wiki",
            "",
            f"Generated from canonical ledgers at `{status['generated_at_et']}`.",
            "",
            "This wiki is generated from the same source used by the public dashboard and repo copy. "
            "It should never carry frozen win-rate, equity, or trade-count claims that drift from the ledgers.",
            "",
            "## Current Snapshot",
            "",
            f"- Public status: `{status['system']['public_status']}`",
            f"- Paper equity: `{_fmt_money(status['paper'].get('equity'))}`",
            f"- Closed trades total: `{ledger.get('closed_trades_total')}`",
            f"- Total realized P/L: `{_fmt_money(ledger.get('total_realized_pnl'))}`",
            f"- Weekly gate mode: `{gate.get('mode')}`",
            "",
            "## Key Links",
            "",
            f"- [Public dashboard]({status['links']['repo'].replace('github.com/IgorGanapolsky/trading', 'igorganapolsky.github.io/trading')})",
            f"- [Operator dashboard]({status['links']['repo'].replace('github.com/IgorGanapolsky/trading', 'igorganapolsky.github.io/trading/rag-query.html')})",
            "- [Progress Dashboard](Progress-Dashboard)",
            "- [Development Engine and Evidence](Development-Engine-and-Evidence)",
            "",
            "## Operating Truth",
            "",
            status["narrative"]["thesis"],
            "",
            "## Current Blocker",
            "",
            f"`{gate.get('blocker_reason', 'n/a')}`",
        ]
    )


def render_development_engine(status: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Development Engine and Evidence",
            "",
            f"Generated from canonical ledgers at `{status['generated_at_et']}`.",
            "",
            "This page explains how public-facing system copy stays congruent with live state.",
            "",
            "## Evidence Surfaces",
            "",
            "- `artifacts/daily_scorecard/latest_daily_scorecard.json` for broker-backed daily status",
            "- `data/system_state.json` for active gate state",
            "- `data/trades.json` for paired-trade ledger stats",
            "- `docs/data/public_status.json` for public pages and wiki rendering",
            "",
            "## Current Public-Copy Rules",
            "",
            "- No frozen portfolio numbers in README, About, or wiki prose",
            "- Public pages render from generated status data or link to canonical live surfaces",
            "- Repo metadata and wiki must match the generated public status bundle",
            "",
            "## Current Operator Summary",
            "",
            f"- Paper equity: `{_fmt_money(status['paper'].get('equity'))}`",
            f"- Total realized P/L ledger: `{_fmt_money(status['ledger'].get('total_realized_pnl'))}`",
            f"- Weekly gate mode: `{status['gate'].get('mode')}`",
            f"- Block new positions: `{status['gate'].get('block_new_positions')}`",
            "",
            "## Exact Blocker",
            "",
            f"`{status['gate'].get('blocker_reason', 'n/a')}`",
        ]
    )


def _write_if_changed(path: Path, content: str) -> bool:
    existing = path.read_text(encoding="utf-8") if path.exists() else None
    if existing == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def write_public_surfaces(repo_root: Path) -> dict[str, bool]:
    status = build_public_status(repo_root)
    changed = {}
    public_status_path = repo_root / "docs/data/public_status.json"
    changed[str(public_status_path.relative_to(repo_root))] = _write_if_changed(
        public_status_path, json.dumps(status, indent=2) + "\n"
    )

    wiki_dir = repo_root / "wiki"
    changed["wiki/Home.md"] = _write_if_changed(wiki_dir / "Home.md", render_home(status) + "\n")
    changed["wiki/Progress-Dashboard.md"] = _write_if_changed(
        wiki_dir / "Progress-Dashboard.md", render_progress_dashboard(status) + "\n"
    )
    changed["wiki/Development-Engine-and-Evidence.md"] = _write_if_changed(
        wiki_dir / "Development-Engine-and-Evidence.md", render_development_engine(status) + "\n"
    )
    return changed


def check_public_surfaces(repo_root: Path) -> int:
    expected_status = build_public_status(repo_root)
    expected_json = json.dumps(expected_status, indent=2) + "\n"
    status_path = repo_root / "docs/data/public_status.json"
    failures: list[str] = []
    actual_status = status_path.read_text(encoding="utf-8") if status_path.exists() else ""

    if actual_status != expected_json:
        failures.append(
            "docs/data/public_status.json is out of date. Run scripts/build_public_status.py."
        )

    expected_pages = {
        "wiki/Home.md": render_home(expected_status) + "\n",
        "wiki/Progress-Dashboard.md": render_progress_dashboard(expected_status) + "\n",
        "wiki/Development-Engine-and-Evidence.md": render_development_engine(expected_status)
        + "\n",
    }
    for rel, content in expected_pages.items():
        path = repo_root / rel
        actual = path.read_text(encoding="utf-8") if path.exists() else ""
        if actual != content:
            failures.append(f"{rel} is out of date. Run scripts/build_public_status.py.")

    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print("Public status artifacts are current.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build public dashboard/wiki status surfaces.")
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--check", action="store_true", help="Fail if outputs are stale.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    if args.check:
        return check_public_surfaces(repo_root)

    changed = write_public_surfaces(repo_root)
    for path, did_change in changed.items():
        print(f"{path} changed={did_change}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
