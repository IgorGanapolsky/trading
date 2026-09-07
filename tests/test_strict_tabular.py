"""Tests for Polars-2 inspired fail-fast tabular helpers (AGENT-589)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.utils.strict_tabular import (
    LosslessCoercionError,
    SchemaError,
    ShapeError,
    assert_equal_heights,
    assert_id_equality,
    collect_row_schema,
    parse_optional_strict_int,
    parse_strict_int,
    strict_horizontal_zip,
)


def test_assert_equal_heights_ok():
    assert assert_equal_heights([1, 2], ["a", "b"], labels=("n", "s")) == 2


def test_assert_equal_heights_raises_instead_of_padding():
    with pytest.raises(ShapeError, match="different heights"):
        assert_equal_heights([1, 2, 3], [1, 2], labels=("left", "right"))


def test_strict_horizontal_zip_ok():
    rows = strict_horizontal_zip({"day": [1, 2], "count": [10, 20]})
    assert rows == [{"day": 1, "count": 10}, {"day": 2, "count": 20}]


def test_strict_horizontal_zip_refuses_silent_pad():
    with pytest.raises(ShapeError):
        strict_horizontal_zip({"day": [1, 2, 3], "flagged": [1, 0]})


def test_parse_strict_int_accepts_int_and_digit_string():
    assert parse_strict_int(12, field="n") == 12
    assert parse_strict_int("7", field="n") == 7
    assert parse_optional_strict_int(None, field="n") is None


def test_parse_strict_int_refuses_float_coercion():
    with pytest.raises(LosslessCoercionError, match="refuse float"):
        parse_strict_int(3.0, field="closed_trades")
    with pytest.raises(LosslessCoercionError, match="non-integer"):
        parse_strict_int(1.5, field="closed_trades")


def test_assert_id_equality_string_safe():
    assert assert_id_equality("9007199254740993", "9007199254740993") == "9007199254740993"
    with pytest.raises(LosslessCoercionError, match="float identity"):
        assert_id_equality(9007199254740993.0, 9007199254740992.0)


def test_collect_row_schema_ok_and_fail():
    rows = [
        {"id": "a", "status": "closed", "realized_pnl": 1.0},
        {"id": "b", "status": "closed", "realized_pnl": -2.0},
    ]
    report = collect_row_schema(
        rows, required=("id", "status", "realized_pnl"), numeric_fields=("realized_pnl",)
    )
    assert report["ok"] is True
    assert report["inspected_rows"] == 2

    with pytest.raises(SchemaError, match="missing_required:id"):
        collect_row_schema(
            [{"status": "closed", "realized_pnl": 1}],
            required=("id", "status"),
        )


def test_trade_evidence_flags_lossy_stats_count():
    from src.analytics import trade_evidence as te

    payload = {
        "trades": [
            {
                "id": "t1",
                "status": "closed",
                "realized_pnl": 10.0,
                "strategy_family": "spy_put_credit",
                "quantity": 1,
                "put_delta": -0.15,
                "exit_reason": "profit_target",
                "strikes": {"short_put": 100, "long_put": 95},
            }
        ],
        "stats": {
            # Float count would previously coerce silently via int(_as_float(...)).
            "closed_trades": 1.0,
            "unpaired_order_count": 0,
            "total_realized_pnl": 10.0,
        },
    }
    evidence = te.build_trade_evidence(payload, strategy_family="spy_put_credit")
    assert any("lossy_stats_count_coercion" in issue for issue in evidence.issues)


def test_strict_ledger_schema_cli_ok(tmp_path: Path):
    from scripts import strict_ledger_schema as cli

    payload = {
        "trades": [
            {"id": "a", "status": "closed", "realized_pnl": 1.25, "quantity": 1},
        ],
        "stats": {"closed_trades": 1, "unpaired_order_count": 0},
    }
    path = tmp_path / "trades.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert cli.main(["--trades", str(path), "--json"]) == 0
