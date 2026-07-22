import json
from argparse import Namespace
from pathlib import Path

from scripts.enforce_promotion_gate import evaluate_gate, evaluate_staleness

FIXTURES = Path("tests/fixtures")


def load_fixture(name: str):
    with (FIXTURES / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def base_args() -> Namespace:
    args = Namespace(
        required_win_rate=60.0,
        required_sharpe=1.5,
        max_drawdown=10.0,
        min_profitable_days=30,
    )
    args.min_trades = 100
    return args


def test_promotion_gate_passes_with_valid_metrics():
    state = load_fixture("system_state_sample.json")
    summary = load_fixture("backtest_summary_sample.json")
    deficits = evaluate_gate(state, summary, base_args())
    assert deficits == []


def test_promotion_gate_flags_low_win_rate():
    state = load_fixture("system_state_sample.json")
    state["performance"]["win_rate"] = 0.4  # 40%
    summary = load_fixture("backtest_summary_sample.json")
    deficits = evaluate_gate(state, summary, base_args())
    assert any("Win rate" in item for item in deficits)


def test_promotion_gate_fails_closed_when_timestamp_is_missing():
    stale_hours, deficits = evaluate_staleness({}, 48.0)

    assert stale_hours is None
    assert any("freshness cannot be verified" in item for item in deficits)


def test_promotion_gate_fails_closed_when_state_is_stale():
    state = {"meta": {"last_updated": "2020-01-01T00:00:00Z"}}
    stale_hours, deficits = evaluate_staleness(state, 48.0)

    assert stale_hours is not None and stale_hours > 48.0
    assert any("refresh evidence before promotion" in item for item in deficits)
