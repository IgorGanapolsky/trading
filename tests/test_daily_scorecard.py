from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from src.analytics import daily_scorecard as daily_scorecard_mod
from src.analytics.daily_scorecard import (
    PositionSnapshot,
    build_daily_scorecard,
    render_daily_scorecard_markdown,
    summarize_open_structures,
    write_daily_scorecard_artifacts,
)


ET = ZoneInfo("America/New_York")


class _FakeClient:
    def __init__(self, account, positions, orders):
        self._account = account
        self._positions = positions
        self._orders = orders

    def get_account(self):
        return self._account

    def get_all_positions(self):
        return self._positions

    def get_orders(self, filter=None):  # noqa: ARG002
        return self._orders


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_summarize_open_structures_groups_option_legs_by_expiry():
    positions = [
        PositionSnapshot("SPY260424C00690000", -1.0, -10.0, 100.0, 2.3, 0.9),
        PositionSnapshot("SPY260424C00700000", 1.0, 5.0, -40.0, 0.8, 0.3),
        PositionSnapshot("SPY260501P00590000", -1.0, 8.0, 120.0, 4.3, 2.9),
        PositionSnapshot("SPY260501P00580000", 1.0, -3.0, -70.0, 3.4, 2.2),
    ]

    structures = summarize_open_structures(positions)

    assert [structure.structure_id for structure in structures] == [
        "SPY 2026-04-24",
        "SPY 2026-05-01",
    ]
    assert structures[0].intraday_pl == -5.0
    assert structures[1].unrealized_pl == 50.0


def test_build_daily_scorecard_derives_realized_from_account_delta(tmp_path: Path):
    repo = tmp_path
    _write_json(
        repo / "data/system_state.json",
        {
            "last_updated": "2026-04-01T12:00:00Z",
            "north_star": {
                "updated_at": "2026-04-01T12:00:00Z",
                "estimated_monthly_after_tax_from_expectancy": 250.0,
                "monthly_target_progress_pct": 4.17,
                "probability_score": 51.0,
                "probability_label": "low",
            },
            "north_star_weekly_gate": {
                "verified_edge_available": False,
                "recommended_max_position_pct": 0.01,
                "reason": "Need more trades.",
                "updated_at": "2026-04-01T12:00:00Z",
                "cadence_kpi": {
                    "qualified_setups_observed": 1,
                    "closed_trades_observed": 0,
                },
                "scaling_sample_gate": {
                    "closed_trades_observed": 2,
                    "min_closed_trades_for_scaling": 30,
                    "passed": False,
                },
            },
        },
    )
    _write_json(
        repo / "data/trades.json",
        {
            "meta": {"last_sync": "2026-04-01T15:00:00Z"},
            "stats": {"closed_trades": 3, "last_updated": "2026-04-01T15:00:00Z"},
            "trades": [
                {
                    "id": "closed-1",
                    "status": "closed",
                    "symbol": "SPY",
                    "signature": "SPY_2026-05-01_P580-610_C680-698",
                    "legs": {"underlying": "SPY", "expiry": "2026-05-01"},
                    "realized_pnl": -329.0,
                    "outcome": "loss",
                    "entry_style": "credit",
                    "exit_style": "debit",
                    "exit_date": "2026-04-01",
                    "exit_time": "2026-04-01T15:06:00+00:00",
                }
            ],
        },
    )

    now = datetime(2026, 4, 1, 10, 30, tzinfo=ET)
    paper_client = _FakeClient(
        SimpleNamespace(equity="1005", last_equity="1000", cash="900", buying_power="1800"),
        [
            SimpleNamespace(
                symbol="SPY260424C00690000",
                qty="-1",
                unrealized_intraday_pl="4",
                unrealized_pl="40",
                avg_entry_price="2.31",
                current_price="0.91",
            ),
            SimpleNamespace(
                symbol="SPY260424C00700000",
                qty="1",
                unrealized_intraday_pl="-1",
                unrealized_pl="-10",
                avg_entry_price="0.82",
                current_price="0.28",
            ),
        ],
        [
            SimpleNamespace(
                id="simple-1",
                symbol="SPY260424C00690000",
                side="sell",
                qty="1",
                filled_qty="1",
                filled_avg_price="0.91",
                order_class="simple",
                filled_at=datetime(2026, 4, 1, 13, 45, tzinfo=timezone.utc),
            ),
            SimpleNamespace(
                id="mleg-1",
                symbol=None,
                side=None,
                qty="1",
                filled_qty="1",
                filled_avg_price="-0.93",
                order_class="mleg",
                filled_at=datetime(2026, 4, 1, 14, 5, tzinfo=timezone.utc),
                legs=[
                    SimpleNamespace(
                        symbol="SPY260501P00600000",
                        side="buy",
                        qty="1",
                        filled_qty="1",
                        filled_avg_price="3.28",
                    ),
                    SimpleNamespace(
                        symbol="SPY260501P00610000",
                        side="sell",
                        qty="1",
                        filled_qty="1",
                        filled_avg_price="4.21",
                    ),
                ],
            ),
        ],
    )
    live_client = _FakeClient(
        SimpleNamespace(equity="20", last_equity="20", cash="20", buying_power="40"),
        [],
        [],
    )

    scorecard = build_daily_scorecard(
        repo,
        now=now,
        paper_client=paper_client,
        live_client=live_client,
        sync_paired_ledger=False,
    )

    assert scorecard["paper"]["total_pnl_today"] == 5.0
    assert scorecard["paper"]["unrealized_pnl_today"] == 3.0
    assert scorecard["paper"]["realized_pnl_today"] == 2.0
    assert (
        scorecard["paper"]["realized_pnl_method"]
        == "derived_from_account_delta_minus_open_position_intraday_marks"
    )
    assert scorecard["paper"]["fills_today_count"] == 2
    assert scorecard["paper"]["fill_legs_today_count"] == 3
    assert (
        "Today's gain comes from open-position repricing $3.00"
        in scorecard["paper"]["why_today"]["summary"]
    )
    assert "realized activity $2.00 across 2 fills" in scorecard["paper"]["why_today"]["summary"]
    assert (
        "biggest structure offset SPY 2026-04-24 $3.00"
        in scorecard["paper"]["why_today"]["summary"]
    )
    assert scorecard["paper"]["why_today"]["top_dragging_structures"] == []
    assert scorecard["paper"]["why_today"]["top_offsetting_structures"] == [
        {
            "structure_id": "SPY 2026-04-24",
            "underlying": "SPY",
            "expiry": "2026-04-24",
            "intraday_pl": 3.0,
            "unrealized_pl": 30.0,
            "legs_count": 2,
        }
    ]
    assert (
        scorecard["paper"]["fill_activity_method"]
        == "exact_filled_order_leg_cash_flows_grouped_by_structure"
    )
    assert scorecard["paper"]["fill_activity_by_structure"] == [
        {
            "structure_id": "SPY 2026-05-01",
            "premium_cash_flow": 93.0,
            "buy_premium_cash_flow": 328.0,
            "sell_premium_cash_flow": 421.0,
            "fills_count": 2,
            "symbols": ["SPY260501P00600000", "SPY260501P00610000"],
        },
        {
            "structure_id": "SPY 2026-04-24",
            "premium_cash_flow": 91.0,
            "buy_premium_cash_flow": 0.0,
            "sell_premium_cash_flow": 91.0,
            "fills_count": 1,
            "symbols": ["SPY260424C00690000"],
        },
    ]
    assert scorecard["paired_closed_trades"]["closed_trades_today_count"] == 1
    assert scorecard["paired_closed_trades"]["exact_realized_pnl_today"] == -329.0
    assert scorecard["paired_closed_trades"]["closed_trades_total"] == 3
    assert scorecard["paired_closed_trade_sync"] == {"attempted": False, "success": None}
    assert scorecard["paired_closed_trades"]["closed_trades_today"] == [
        {
            "trade_id": "closed-1",
            "structure_id": "SPY 2026-05-01",
            "signature": "SPY_2026-05-01_P580-610_C680-698",
            "realized_pnl": -329.0,
            "outcome": "loss",
            "entry_style": "credit",
            "exit_style": "debit",
            "exit_time": "2026-04-01T11:06:00-04:00",
        }
    ]
    assert scorecard["north_star"]["scale_allowed"] is False
    assert scorecard["north_star"]["stale"] is False


def test_write_daily_scorecard_artifacts_and_markdown(tmp_path: Path):
    repo = tmp_path
    _write_json(
        repo / "data/system_state.json",
        {
            "last_updated": "2026-03-26T14:51:13Z",
            "north_star_weekly_gate": {
                "reason": "Cadence miss.",
                "verified_edge_available": False,
                "recommended_max_position_pct": 0.01,
                "cadence_kpi": {
                    "qualified_setups_observed": 0,
                    "closed_trades_observed": 0,
                },
                "scaling_sample_gate": {
                    "closed_trades_observed": 1,
                    "min_closed_trades_for_scaling": 30,
                    "passed": False,
                },
            },
            "north_star": {
                "estimated_monthly_after_tax_from_expectancy": 123.0,
                "monthly_target_progress_pct": 2.05,
            },
        },
    )
    now = datetime(2026, 4, 1, 10, 47, tzinfo=ET)
    paper_client = _FakeClient(
        SimpleNamespace(equity="95401.35", last_equity="95428.35", cash="0", buying_power="0"),
        [],
        [],
    )
    live_client = _FakeClient(
        SimpleNamespace(equity="0", last_equity="0", cash="0", buying_power="0"), [], []
    )

    json_out = repo / "artifacts/daily_scorecard/latest_daily_scorecard.json"
    md_out = repo / "artifacts/daily_scorecard/latest_daily_scorecard.md"
    scorecard = write_daily_scorecard_artifacts(
        repo,
        json_out=json_out,
        markdown_out=md_out,
        now=now,
        paper_client=paper_client,
        live_client=live_client,
        sync_paired_ledger=False,
    )

    assert json_out.exists()
    assert md_out.exists()
    text = md_out.read_text(encoding="utf-8")
    assert "Paper total P/L: `-$27.00`" in text
    assert "Paper realized method: `exact_from_account_delta_no_fills`" in text
    assert "Exact blocker: `Cadence miss.`" in text
    assert "North Star snapshot stale: `True`" in text
    assert "## Fill Attribution" in text
    assert "## Paired Ledger Sync" in text
    assert "## Exact Closed Structures Today" in text
    assert scorecard["paper"]["realized_pnl_today"] == -27.0


def test_render_daily_scorecard_markdown_includes_structure_lines():
    scorecard = {
        "generated_at_et": "2026-04-01T10:47:14-04:00",
        "paper": {
            "realized_pnl_today": 0.0,
            "realized_pnl_method": "exact_from_account_delta_no_fills",
            "unrealized_pnl_today": -27.0,
            "total_pnl_today": -27.0,
            "fills_today_count": 0,
            "fill_legs_today_count": 0,
            "fill_activity_method": "exact_filled_order_leg_cash_flows_grouped_by_structure",
            "fill_activity_by_structure": [
                {
                    "structure_id": "SPY 2026-05-01",
                    "premium_cash_flow": -329.0,
                    "buy_premium_cash_flow": 1459.0,
                    "sell_premium_cash_flow": 1130.0,
                    "fills_count": 9,
                }
            ],
            "equity": 95401.35,
            "why_today": {
                "summary": "Today's loss comes from open-position repricing -$27.00. Drivers: biggest structure drag SPY 2026-05-01 -$44.00; biggest structure offset SPY 2026-04-24 $17.00; biggest leg drag SPY260501C00680000 -$80.00; biggest leg offset SPY260424P00625000 $70.00.",
                "filled_orders_today_count": 0,
                "top_dragging_structures": [
                    {
                        "structure_id": "SPY 2026-05-01",
                        "intraday_pl": -44.0,
                        "unrealized_pl": -89.0,
                        "legs_count": 8,
                    }
                ],
                "top_offsetting_structures": [
                    {
                        "structure_id": "SPY 2026-04-24",
                        "intraday_pl": 17.0,
                        "unrealized_pl": 99.0,
                        "legs_count": 4,
                    }
                ],
                "top_dragging_legs": [
                    {
                        "symbol": "SPY260501C00680000",
                        "qty": -1.0,
                        "intraday_pl": -80.0,
                        "unrealized_pl": -82.0,
                    }
                ],
                "top_offsetting_legs": [
                    {
                        "symbol": "SPY260424P00625000",
                        "qty": -1.0,
                        "intraday_pl": 70.0,
                        "unrealized_pl": 118.0,
                    }
                ],
            },
            "open_structures": [
                {
                    "structure_id": "SPY 2026-04-24",
                    "intraday_pl": 17.0,
                    "unrealized_pl": 99.0,
                    "legs": [{}, {}, {}, {}],
                }
            ],
        },
        "live": {"total_pnl_today": 0.0, "equity": 0.0},
        "paired_closed_trade_sync": {
            "attempted": True,
            "success": True,
            "changed": False,
            "new_closed": 0,
            "closed_total": 3,
            "error": None,
        },
        "paired_closed_trades": {
            "closed_trades_today_count": 1,
            "exact_realized_pnl_today": -329.0,
            "closed_trades_total": 3,
            "ledger_last_updated": "2026-04-01T15:00:00Z",
            "closed_trades_today": [
                {
                    "structure_id": "SPY 2026-05-01",
                    "realized_pnl": -329.0,
                    "outcome": "loss",
                    "exit_time": "2026-04-01T11:06:00-04:00",
                }
            ],
        },
        "north_star": {
            "estimated_monthly_after_tax": 123.0,
            "monthly_target_progress_pct": 2.05,
            "qualified_setups_this_week": 0,
            "closed_trades_this_week": 0,
            "verified_edge_available": False,
            "scale_allowed": False,
            "recommended_max_position_pct": 0.01,
            "scaling_gate_closed_trades_observed": 1,
            "scaling_gate_min_closed_trades": 30,
            "blocker_reason": "Need more trades.",
            "stale": True,
        },
    }

    markdown = render_daily_scorecard_markdown(scorecard)

    assert "SPY 2026-04-24" in markdown
    assert "Paper unrealized P/L: `-$27.00`" in markdown
    assert "Paper realized method" in markdown
    assert "## Why Today" in markdown
    assert "Today's loss comes from open-position repricing -$27.00." in markdown
    assert "biggest structure drag SPY 2026-05-01 -$44.00" in markdown
    assert "SPY260501C00680000" in markdown
    assert "## Fill Attribution" in markdown
    assert "net premium cash flow `-$329.00`" in markdown
    assert "## Paired Ledger Sync" in markdown
    assert "Sync attempted: `True`" in markdown
    assert "## Exact Closed Structures Today" in markdown
    assert "exact realized P/L `-$329.00`" in markdown
    assert "Scale allowed: `False`" in markdown


def test_write_daily_scorecard_artifacts_syncs_paired_ledger(monkeypatch, tmp_path: Path):
    import scripts.sync_closed_positions as sync_closed

    repo = tmp_path
    monkeypatch.setattr(sync_closed, "_fetch_broker_trade_history", lambda limit=1000: [])
    _write_json(
        repo / "data/system_state.json",
        {
            "trade_history": [
                {
                    "id": "entry-1",
                    "filled_at": "2026-04-01T14:30:00+00:00",
                    "side": "sell",
                    "qty": 1,
                    "price": 2.5,
                    "legs": [
                        "SPY260501P00580000",
                        "SPY260501P00590000",
                        "SPY260501C00680000",
                        "SPY260501C00690000",
                    ],
                },
                {
                    "id": "exit-1",
                    "filled_at": "2026-04-01T18:30:00+00:00",
                    "side": "buy",
                    "qty": 1,
                    "price": 1.25,
                    "legs": [
                        "SPY260501P00580000",
                        "SPY260501P00590000",
                        "SPY260501C00680000",
                        "SPY260501C00690000",
                    ],
                },
            ]
        },
    )
    _write_json(
        repo / "data/trades.json",
        {
            "meta": {"last_sync": "2026-03-31T12:00:00Z"},
            "stats": {"closed_trades": 0, "last_updated": "2026-03-31T12:00:00Z"},
            "trades": [],
        },
    )

    now = datetime(2026, 4, 1, 15, 0, tzinfo=ET)
    paper_client = _FakeClient(
        SimpleNamespace(equity="1000", last_equity="1000", cash="1000", buying_power="2000"),
        [],
        [],
    )
    live_client = _FakeClient(
        SimpleNamespace(equity="0", last_equity="0", cash="0", buying_power="0"), [], []
    )

    scorecard = write_daily_scorecard_artifacts(
        repo,
        json_out=repo / "artifacts/daily_scorecard/latest_daily_scorecard.json",
        markdown_out=repo / "artifacts/daily_scorecard/latest_daily_scorecard.md",
        now=now,
        paper_client=paper_client,
        live_client=live_client,
        sync_paired_ledger=True,
    )

    assert scorecard["paired_closed_trade_sync"]["attempted"] is True
    assert scorecard["paired_closed_trade_sync"]["success"] is True
    assert scorecard["paired_closed_trade_sync"]["new_closed"] == 1
    assert scorecard["paired_closed_trade_sync"]["closed_total"] == 1
    assert scorecard["paired_closed_trades"]["closed_trades_today_count"] == 1
    assert scorecard["paired_closed_trades"]["exact_realized_pnl_today"] == 125.0
    assert (
        scorecard["paired_closed_trades"]["closed_trades_today"][0]["structure_id"]
        == "SPY 2026-05-01"
    )


def test_daily_scorecard_helper_error_paths(monkeypatch, tmp_path: Path):
    broken = tmp_path / "broken.json"
    broken.write_text("{bad", encoding="utf-8")

    assert daily_scorecard_mod._as_float("bad", default=7.5) == 7.5
    assert daily_scorecard_mod._load_json(broken, {"ok": False}) == {"ok": False}
    assert daily_scorecard_mod._parse_iso("nope") is None
    assert daily_scorecard_mod._parse_iso("2026-04-01T12:00:00").tzinfo is not None
    assert daily_scorecard_mod._normalize_side("OrderSide.sell") == "SELL"
    assert (
        daily_scorecard_mod._signed_premium_cash_flow("SPY260424C00690000", 1, 1.25, "hold") == 0.0
    )
    assert daily_scorecard_mod._group_structure_key("custom-symbol") == (
        "CUSTOM-SYMBOL",
        None,
        "CUSTOM-SYMBOL",
    )

    now = datetime(2026, 4, 2, 10, 0, tzinfo=ET)
    assert daily_scorecard_mod._filled_today(SimpleNamespace(filled_at=None), now) is None
    assert (
        daily_scorecard_mod._fill_from_order(
            SimpleNamespace(
                symbol="SPY260424C00690000",
                side="buy",
                qty="1",
                filled_qty="1",
                filled_avg_price="1.0",
                order_class="simple",
                filled_at=datetime(2026, 4, 1, 13, 0, tzinfo=timezone.utc),
            ),
            now,
        )
        is None
    )
    assert (
        daily_scorecard_mod._flatten_fill_legs_from_order(
            SimpleNamespace(legs=None, filled_at=datetime(2026, 4, 1, 13, 0, tzinfo=timezone.utc)),
            now,
        )
        == []
    )

    _write_json(tmp_path / "data/system_state.json", ["bad-state"])
    _write_json(tmp_path / "data/trades.json", ["bad-ledger"])
    north_star = daily_scorecard_mod._load_north_star_status(tmp_path, now)
    paired = daily_scorecard_mod._load_paired_closed_trade_status(tmp_path, now)
    assert north_star == {"available": False, "reason": "system_state.json missing or invalid"}
    assert paired == {"available": False, "reason": "trades.json missing or invalid"}

    assert daily_scorecard_mod._paired_trade_structure_id({"signature": "SPY"}) == "SPY"
    assert daily_scorecard_mod._paired_trade_structure_id({"symbol": "QQQ"}) == "QQQ"

    monkeypatch.setattr(
        daily_scorecard_mod.importlib,
        "import_module",
        lambda name: (_ for _ in ()).throw(ImportError("boom")),
    )
    assert daily_scorecard_mod._sync_paired_closed_trade_ledger(tmp_path) == {
        "attempted": True,
        "success": False,
        "error": "import_failed: boom",
    }


def test_daily_scorecard_sync_and_client_branches(monkeypatch, tmp_path: Path):
    class FakeTradingClient:
        def __init__(self, api_key, secret_key, *, paper):
            self.api_key = api_key
            self.secret_key = secret_key
            self.paper = paper

    monkeypatch.setattr("alpaca.trading.client.TradingClient", FakeTradingClient)
    client = daily_scorecard_mod._create_client(("key", "secret"), paper=True)
    assert isinstance(client, FakeTradingClient)
    assert client.paper is True
    assert daily_scorecard_mod._create_client((None, "secret"), paper=True) is None

    class FakeSyncModule:
        PROJECT_ROOT = None
        DATA_DIR = None
        SYSTEM_STATE_FILE = None
        TRADES_FILE = None

        @staticmethod
        def sync_closed_positions(dry_run=False):  # noqa: ARG004
            return "not-a-dict"

    monkeypatch.setattr(daily_scorecard_mod.importlib, "import_module", lambda name: FakeSyncModule)
    non_dict = daily_scorecard_mod._sync_paired_closed_trade_ledger(tmp_path)
    assert non_dict["attempted"] is True
    assert non_dict["success"] is False
    assert non_dict["error"] == "sync_returned_non_dict"

    class RaisingSyncModule(FakeSyncModule):
        @staticmethod
        def sync_closed_positions(dry_run=False):  # noqa: ARG004
            raise RuntimeError("sync exploded")

    monkeypatch.setattr(
        daily_scorecard_mod.importlib, "import_module", lambda name: RaisingSyncModule
    )
    exploded = daily_scorecard_mod._sync_paired_closed_trade_ledger(tmp_path)
    assert exploded["attempted"] is True
    assert exploded["success"] is False
    assert exploded["error"] == "sync exploded"


def test_build_daily_scorecard_without_credentials_and_with_filtered_trades(
    monkeypatch, tmp_path: Path
):
    now = datetime(2026, 4, 2, 12, 0, tzinfo=ET)
    _write_json(
        tmp_path / "data/system_state.json",
        {
            "north_star_weekly_gate": {
                "verified_edge_available": True,
                "recommended_max_position_pct": 0.02,
                "reason": "Ready.",
                "cadence_kpi": {"qualified_setups_observed": 4, "closed_trades_observed": 3},
                "scaling_sample_gate": {
                    "closed_trades_observed": 40,
                    "min_closed_trades_for_scaling": 30,
                    "passed": True,
                },
            }
        },
    )
    _write_json(
        tmp_path / "data/trades.json",
        {
            "meta": {"last_sync": "2026-04-02T10:00:00Z"},
            "stats": {"closed_trades": 9},
            "trades": [
                "not-a-dict",
                {"status": "open", "exit_date": "2026-04-02"},
                {"status": "closed", "exit_date": "2026-04-01", "realized_pnl": -12.0},
                {
                    "status": "closed",
                    "signature": "SPY_2026-04-02_P580-590_C610-620",
                    "realized_pnl": 44.0,
                    "outcome": "win",
                    "exit_date": "2026-04-02",
                },
            ],
        },
    )

    monkeypatch.setattr(daily_scorecard_mod, "get_alpaca_credentials", lambda: (None, None))
    monkeypatch.setattr(daily_scorecard_mod, "get_brokerage_credentials", lambda: (None, None))

    scorecard = build_daily_scorecard(tmp_path, now=now, sync_paired_ledger=False)

    assert scorecard["paper"] == {
        "available": False,
        "reason": "Paper Alpaca credentials not available.",
    }
    assert scorecard["live"] == {
        "available": False,
        "reason": "Live Alpaca credentials not available.",
    }
    assert scorecard["north_star"]["scale_allowed"] is True
    assert scorecard["paired_closed_trades"]["closed_trades_today_count"] == 1
    assert scorecard["paired_closed_trades"]["exact_realized_pnl_today"] == 44.0
    assert (
        scorecard["paired_closed_trades"]["closed_trades_today"][0]["structure_id"]
        == "SPY 2026-04-02"
    )


def test_summarize_why_today_loss_flat_and_no_driver_paths():
    loss_positions = [PositionSnapshot("SPY260424C00690000", -1.0, -8.0, -8.0, 2.0, 2.1)]
    loss_structures = summarize_open_structures(loss_positions)
    loss = daily_scorecard_mod._summarize_why_today(
        loss_positions,
        loss_structures,
        [],
        total_change=-8.0,
        realized_today=0.0,
        unrealized_today=-8.0,
    )
    assert loss["summary"].startswith("Today's loss comes from ")
    assert "biggest structure drag SPY 2026-04-24 -$8.00" in loss["summary"]

    flat = daily_scorecard_mod._summarize_why_today(
        [],
        [],
        [],
        total_change=0.0,
        realized_today=0.0,
        unrealized_today=0.0,
    )
    assert flat["summary"] == "No open positions are contributing to today's move."

    flat_with_positions = daily_scorecard_mod._summarize_why_today(
        [PositionSnapshot("SPY260424C00690000", -1.0, 0.0, 0.0, 2.0, 2.0)],
        summarize_open_structures(
            [PositionSnapshot("SPY260424C00690000", -1.0, 0.0, 0.0, 2.0, 2.0)]
        ),
        [],
        total_change=0.0,
        realized_today=0.0,
        unrealized_today=0.0,
    )
    assert (
        flat_with_positions["summary"]
        == "Today's flat result comes from open-position repricing $0.00."
    )
