"""Tests for Precious Metals Strategy."""

from src.strategies.precious_metals_strategy import PreciousMetalsStrategy


class TestPreciousMetalsStrategy:
    def test_init(self):
        strategy = PreciousMetalsStrategy()
        assert strategy.tickers == ["GLD", "SLV"]
        assert strategy.enabled is False

    def test_analyze_disabled(self):
        strategy = PreciousMetalsStrategy()
        result = strategy.analyze()

        assert result["status"] == "disabled"
        assert result["recommendation"] == "HOLD"

    def test_execute_disabled(self):
        strategy = PreciousMetalsStrategy()
        result = strategy.execute()

        assert result["success"] is True
        assert result["trades_executed"] == 0
