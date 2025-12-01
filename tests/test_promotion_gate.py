import json
from argparse import Namespace
from pathlib import Path

from scripts.enforce_promotion_gate import evaluate_gate


FIXTURES = Path("tests/fixtures")


def load_fixture(name: str):
    with (FIXTURES / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def base_args() -> Namespace:
    return Namespace(
        required_win_rate=60.0,
        required_sharpe=1.5,
        max_drawdown=10.0,
        min_profitable_days=30,
    )


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
