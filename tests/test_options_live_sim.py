import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from src.analytics.options_live_sim import OptionsLiveSimResult, OptionsLiveSimulator
from src.analytics.options_profit_planner import OptionsProfitPlanner


class DummyThetaExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[float, str, list[str]]] = []

    def generate_theta_plan(
        self,
        *,
        account_equity: float,
        regime_label: str,
        symbols: list[str],
    ) -> dict[str, object]:
        self.calls.append((account_equity, regime_label, symbols))
        return {
            "summary": "theta ready",
            "opportunities": [
                {
                    "symbol": symbols[0],
                    "strategy": "test",
                    "contracts": 1,
                    "estimated_premium": 35.0,
                }
            ],
            "total_estimated_premium": 5.0,
            "premium_gap": 5.0,
        }


def _write_system_state(path: Path, equity: float) -> None:
    payload = {
        "account": {
            "current_equity": equity,
        }
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_load_account_equity_reads_system_state(tmp_path: Path) -> None:
    state_path = tmp_path / "system_state.json"
    _write_system_state(state_path, 1234.56)

    sim = OptionsLiveSimulator(
        system_state_path=state_path,
        snapshot_dir=tmp_path / "signals",
        planner=MagicMock(),
        theta_executor=MagicMock(),
    )

    assert pytest.approx(sim.load_account_equity()) == 1234.56


def test_run_combines_planner_and_theta(tmp_path: Path) -> None:
    snapshot_dir = tmp_path / "snapshots"
    planner = OptionsProfitPlanner(snapshot_dir=snapshot_dir)
    theta = DummyThetaExecutor()
    simulator = OptionsLiveSimulator(
        system_state_path=tmp_path / "missing.json",
        snapshot_dir=snapshot_dir,
        planner=planner,
        theta_executor=theta,
    )

    snapshot = {
        "call_opportunities": [
            {
                "symbol": "SPY",
                "signal_type": "call",
                "strike": 500,
                "expiration": "2030-01-01",
                "contracts": 1,
                "premium": 0.5,
                "days_to_expiry": 5,
            }
        ],
        "put_opportunities": [],
    }

    result = simulator.run(
        account_equity=6000,
        regime_label="calm",
        snapshot=snapshot,
        symbols=["SPY"],
        persist_summary=False,
    )

    assert result.account_equity == 6000
    assert result.theta_plan["summary"] == "theta ready"
    assert theta.calls[0][1] == "calm"
    assert result.profit_summary["signals_analyzed"] == 1


def test_persist_combined_plan(tmp_path: Path) -> None:
    snapshot_dir = tmp_path / "signals"
    simulator = OptionsLiveSimulator(
        system_state_path=tmp_path / "missing.json",
        snapshot_dir=snapshot_dir,
        planner=MagicMock(),
        theta_executor=MagicMock(),
    )
    result = OptionsLiveSimResult(
        account_equity=5000,
        regime_label="calm",
        regime_source="override",
        theta_plan={"summary": "ok"},
        profit_summary={"target_daily_profit": 10, "signals_analyzed": 0},
    )

    output_path = simulator.persist_combined_plan(result, tmp_path / "combined.json")
    assert output_path.exists()

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["theta_plan"]["summary"] == "ok"
    assert data["regime"]["source"] == "override"
