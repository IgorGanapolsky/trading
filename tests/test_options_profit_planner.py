import json
from pathlib import Path

import pytest
from src.analytics.options_profit_planner import OptionsProfitPlanner
from src.strategies.rule_one_options import RuleOneOptionsSignal


def make_signal(
    symbol: str,
    signal_type: str,
    premium: float,
    contracts: int,
    days_to_expiry: int,
) -> RuleOneOptionsSignal:
    return RuleOneOptionsSignal(
        symbol=symbol,
        signal_type=signal_type,
        strike=100.0,
        expiration="2025-01-17",
        premium=premium,
        annualized_return=0.18,
        sticker_price=150.0,
        mos_price=75.0,
        current_price=110.0,
        rationale="test",
        confidence=0.8,
        contracts=contracts,
        total_premium=premium * 100 * contracts,
        iv_rank=25.0,
        delta=-0.2 if signal_type == "sell_put" else 0.2,
        days_to_expiry=days_to_expiry,
    )


class TestOptionsProfitPlanner:
    def test_summary_computes_gap_and_recommendations(self):
        planner = OptionsProfitPlanner(target_daily_profit=10.0)
        put_signal = make_signal("AAPL", "sell_put", premium=1.0, contracts=1, days_to_expiry=25)
        call_signal = make_signal("MSFT", "sell_call", premium=0.5, contracts=2, days_to_expiry=30)

        summary = planner.summarize([put_signal], [call_signal])

        # Premium pacing: (1*100)/25 = $4/day + (0.5*100*2)/30 ≈ $3.33/day = $7.33/day total
        assert summary["daily_run_rate"] == pytest.approx(7.33, rel=0.01)
        assert summary["gap_to_target"] == pytest.approx(2.67, rel=0.01)
        recommendation = summary["recommendation"]
        assert recommendation is not None
        assert recommendation["additional_contracts_needed"] >= 1
        assert "suggested_action" in recommendation

    def test_build_summary_from_snapshot_handles_empty_payload(self):
        planner = OptionsProfitPlanner()
        snapshot = {
            "put_opportunities": [],
            "call_opportunities": [],
            "_source_path": "data/options_signals/2025-12-01.json",
        }

        summary = planner.build_summary_from_snapshot(snapshot)

        assert summary["signals_analyzed"] == 0
        assert summary["gap_to_target"] == planner.target_daily_profit
        assert "Snapshot contains zero opportunities" in summary["notes"][0]

    def test_persist_summary_writes_file(self, tmp_path: Path):
        planner = OptionsProfitPlanner(snapshot_dir=tmp_path)
        signal = make_signal("NVDA", "sell_put", premium=1.2, contracts=1, days_to_expiry=30)
        summary = planner.summarize([signal], [])

        output_path = planner.persist_summary(summary)
        assert output_path.exists()

        with output_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        assert payload["daily_run_rate"] == summary["daily_run_rate"]
