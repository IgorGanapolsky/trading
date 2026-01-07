"""Tests for Profit Target Tracker."""

import pytest
from unittest.mock import MagicMock

from src.analytics.profit_target_tracker import (
    ProfitTargetTracker,
    ProfitTargetResult,
)


class TestProfitTargetResult:
    def test_default_values(self):
        result = ProfitTargetResult()
        assert result.daily_target == 100.0
        assert result.current_profit == 0.0
        assert result.on_track is False


class TestProfitTargetTracker:
    def test_init(self):
        tracker = ProfitTargetTracker(daily_target=50.0)
        assert tracker.daily_target == 50.0

    def test_check_status(self):
        tracker = ProfitTargetTracker()
        trader = MagicMock()
        trader.get_account_info.return_value = {"unrealized_pl": 75.0}
        
        result = tracker.check_status(trader)
        
        assert result.current_profit == 75.0
        assert result.on_track is True

    def test_get_recommendation_target_met(self):
        tracker = ProfitTargetTracker()
        result = ProfitTargetResult(daily_target=100, current_profit=150)
        
        rec = tracker.get_recommendation(result)
        
        assert "TARGET_MET" in rec
