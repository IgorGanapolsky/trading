#!/usr/bin/env python3
"""Freedom Builder welcome-pack ops CLI (process only — not stock picks).

Usage:
  .venv/bin/python scripts/freedom_builder_ops.py start-here
  .venv/bin/python scripts/freedom_builder_ops.py plan
  .venv/bin/python scripts/freedom_builder_ops.py scenario-10k --stake 10000
  .venv/bin/python scripts/freedom_builder_ops.py portfolio
  .venv/bin/python scripts/freedom_builder_ops.py monthly-income
  .venv/bin/python scripts/freedom_builder_ops.py wednesday
  .venv/bin/python scripts/freedom_builder_ops.py full --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.analytics.freedom_builder_ops import (  # noqa: E402
    build_full_ops_report,
    monthly_income_report,
    portfolio_transparency,
    render_start_here_markdown,
    render_wednesday_markdown,
    scenario_10k,
    score_plan,
    start_here_pack,
    wednesday_free_issue,
)

from scripts.put_credit_cohort_scorecard import (  # noqa: E402
    _is_closed,
    _is_put_credit_trade,
    _load_json,
    _trade_rows,
    build_scorecard,
)

SYSTEM_STATE = ROOT / "data" / "system_state.json"
DEFAULT_TRADES = ROOT / "data" / "trades.json"
DEFAULT_AUDIT = ROOT / "data" / "audit"


def _paper_equity() -> float | None:
    if not SYSTEM_STATE.is_file():
        return None
    try:
        d = json.loads(SYSTEM_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    for key in ("paper_account", "portfolio", "account"):
        block = d.get(key)
        if isinstance(block, dict):
            for k in ("equity", "current_equity", "portfolio_value"):
                if block.get(k) is not None:
                    try:
                        return float(block[k])
                    except (TypeError, ValueError):
                        pass
    return None


def _closed_put_credit_rows() -> list[dict[str, Any]]:
    payload = _load_json(DEFAULT_TRADES)
    rows = _trade_rows(payload)
    return [r for r in rows if _is_put_credit_trade(r) and _is_closed(r)]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "command",
        choices=[
            "start-here",
            "plan",
            "scenario-10k",
            "portfolio",
            "monthly-income",
            "bts",
            "wednesday",
            "full",
        ],
    )
    p.add_argument("--json", action="store_true")
    p.add_argument("--stake", type=float, default=10_000.0)
    p.add_argument("--year", type=int, default=None)
    p.add_argument("--month", type=int, default=None)
    p.add_argument("--inventory-unclean", action="store_true")
    p.add_argument("--out-dir", type=Path, default=DEFAULT_AUDIT)
    args = p.parse_args()

    inventory_clean = not args.inventory_unclean
    paper = _paper_equity()
    closed_rows = _closed_put_credit_rows()

    if args.command == "start-here":
        pack = start_here_pack()
        md = render_start_here_markdown(pack)
        out_j = args.out_dir / "freedom_builder_start_here_latest.json"
        out_m = args.out_dir / "freedom_builder_start_here_latest.md"
        _write(out_j, json.dumps(pack, indent=2, default=str) + "\n")
        _write(out_m, md + "\n")
        print(json.dumps(pack, indent=2, default=str) if args.json else md)
        return 0

    card = build_scorecard()

    if args.command == "plan":
        out = score_plan(scorecard=card, inventory_clean=inventory_clean)
        _write(
            args.out_dir / "freedom_builder_plan_latest.json",
            json.dumps(out, indent=2, default=str) + "\n",
        )
        if args.json:
            print(json.dumps(out, indent=2, default=str))
        else:
            print(f"PLAN total={out['total_score']}/100 band={out['band']}")
            for d in out["dimensions"]:
                print(f"  {d['letter']} {d['name']}: {d['score']}/{d['max_score']}")
                failed = [k for k, v in (d.get("checks") or {}).items() if not v]
                if failed:
                    print(f"    failed: {failed}")
        return 0

    if args.command == "scenario-10k":
        out = scenario_10k(stake=args.stake)
        _write(
            args.out_dir / "freedom_builder_scenario_10k_latest.json",
            json.dumps(out, indent=2, default=str) + "\n",
        )
        print(json.dumps(out, indent=2, default=str))
        return 0

    if args.command == "portfolio":
        out = portfolio_transparency(card, paper_equity=paper)
        _write(
            args.out_dir / "freedom_builder_portfolio_latest.json",
            json.dumps(out, indent=2, default=str) + "\n",
        )
        print(json.dumps(out, indent=2, default=str))
        return 0

    if args.command == "monthly-income":
        out = monthly_income_report(closed_rows, year=args.year, month=args.month)
        _write(
            args.out_dir / "freedom_builder_monthly_income_latest.json",
            json.dumps(out, indent=2, default=str) + "\n",
        )
        print(json.dumps(out, indent=2, default=str))
        return 0

    if args.command == "bts":
        from src.analytics.freedom_builder_ops import behind_the_scenes_decisions

        out = behind_the_scenes_decisions(card, closed_rows)
        _write(
            args.out_dir / "freedom_builder_bts_latest.json",
            json.dumps(out, indent=2, default=str) + "\n",
        )
        print(json.dumps(out, indent=2, default=str))
        return 0

    if args.command == "wednesday":
        issue = wednesday_free_issue(
            card,
            paper_equity=paper,
            closed_rows=closed_rows,
            inventory_clean=inventory_clean,
            stake_for_scenario=args.stake,
        )
        md = render_wednesday_markdown(issue)
        out_j = args.out_dir / "freedom_builder_wednesday_latest.json"
        out_m = args.out_dir / "freedom_builder_wednesday_latest.md"
        _write(out_j, json.dumps(issue, indent=2, default=str) + "\n")
        _write(out_m, md + "\n")
        print(json.dumps(issue, indent=2, default=str) if args.json else md)
        print(f"\njson_out={out_j}\nmd_out={out_m}")
        return 0

    # full
    report = build_full_ops_report(
        card,
        closed_rows=closed_rows,
        paper_equity=paper,
        inventory_clean=inventory_clean,
        stake=args.stake,
    )
    out_j = args.out_dir / "freedom_builder_ops_latest.json"
    _write(out_j, json.dumps(report, indent=2, default=str) + "\n")
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(render_start_here_markdown(report["start_here"]))
        print("---")
        print(render_wednesday_markdown(report["wednesday_issue"]))
        print(f"\njson_out={out_j}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
