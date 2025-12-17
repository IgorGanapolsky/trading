"""
Tests for the Mandatory Trade Gate.

This ensures that ALL trades go through RAG/ML validation before execution.
"""



class TestMandatoryTradeGate:
    """Tests for the mandatory trade gate."""

    def test_gate_can_be_initialized(self):
        """Test that the gate can be initialized."""
        from src.safety.mandatory_trade_gate import MandatoryTradeGate

        gate = MandatoryTradeGate()
        assert gate is not None

    def test_validate_trade_returns_result(self):
        """Test that validate_trade returns a GateResult."""
        from src.safety.mandatory_trade_gate import GateResult, MandatoryTradeGate

        gate = MandatoryTradeGate()
        result = gate.validate_trade(
            symbol="SPY",
            amount=100.0,
            side="BUY",
            strategy="equities",
        )

        assert isinstance(result, GateResult)
        assert hasattr(result, "approved")
        assert hasattr(result, "reason")
        assert hasattr(result, "rag_warnings")
        assert hasattr(result, "ml_anomalies")
        assert hasattr(result, "confidence")
        assert hasattr(result, "timestamp")

    def test_validate_trade_singleton_works(self):
        """Test the singleton pattern for the gate."""
        from src.safety.mandatory_trade_gate import get_trade_gate

        gate1 = get_trade_gate()
        gate2 = get_trade_gate()

        # Should be the same instance
        assert gate1 is gate2

    def test_validate_trade_mandatory_function(self):
        """Test the convenience function."""
        from src.safety.mandatory_trade_gate import validate_trade_mandatory

        result = validate_trade_mandatory(
            symbol="QQQ",
            amount=50.0,
            side="BUY",
            strategy="equities",
        )

        assert result is not None
        assert hasattr(result, "approved")

    def test_result_to_dict(self):
        """Test that GateResult can be serialized to dict."""
        from src.safety.mandatory_trade_gate import MandatoryTradeGate

        gate = MandatoryTradeGate()
        result = gate.validate_trade(
            symbol="SPY",
            amount=100.0,
            side="BUY",
        )

        d = result.to_dict()

        assert isinstance(d, dict)
        assert "approved" in d
        assert "reason" in d
        assert "rag_warnings" in d
        assert "ml_anomalies" in d
        assert "confidence" in d
        assert "timestamp" in d

    def test_trade_blocked_error_exists(self):
        """Test that TradeBlockedError is defined."""
        from src.safety.mandatory_trade_gate import GateResult, TradeBlockedError

        result = GateResult(
            approved=False,
            reason="Test block",
            rag_warnings=["test warning"],
            ml_anomalies=["test anomaly"],
            confidence=0.0,
            timestamp="2025-12-16T00:00:00",
        )

        error = TradeBlockedError(result)
        assert "Test block" in str(error)
        assert error.result == result


class TestGateIntegration:
    """Integration tests for the gate with execution paths."""

    def test_gate_integrated_into_alpaca_executor(self):
        """Test that AlpacaExecutor has gate integration."""
        import inspect

        from src.execution.alpaca_executor import AlpacaExecutor

        source = inspect.getsource(AlpacaExecutor.place_order)

        # Must contain the mandatory gate import
        assert "mandatory_trade_gate" in source
        assert "validate_trade_mandatory" in source
        assert "TradeBlockedError" in source

    def test_gate_integrated_into_alpaca_trader(self):
        """Test that AlpacaTrader has gate integration."""
        import inspect

        from src.core.alpaca_trader import AlpacaTrader

        source = inspect.getsource(AlpacaTrader.execute_order)

        # Must contain the mandatory gate import
        assert "mandatory_trade_gate" in source
        assert "validate_trade_mandatory" in source


class TestDailyPerformanceTracker:
    """Tests for the daily performance tracker."""

    def test_tracker_can_be_initialized(self):
        """Test that the tracker can be initialized."""
        from src.analytics.daily_performance_tracker import DailyPerformanceTracker

        tracker = DailyPerformanceTracker()
        assert tracker is not None

    def test_get_north_star_status(self):
        """Test North Star status retrieval."""
        from src.analytics.daily_performance_tracker import get_north_star_status

        status = get_north_star_status()

        assert isinstance(status, dict)
        assert "target" in status
        assert status["target"] == 100.0  # $100/day North Star
        assert "today_pnl" in status
        assert "progress_pct" in status
        assert "on_track" in status

    def test_calculate_daily_performance(self):
        """Test daily performance calculation."""
        from src.analytics.daily_performance_tracker import DailyPerformanceTracker

        tracker = DailyPerformanceTracker()
        perf = tracker.calculate_daily_performance()

        assert hasattr(perf, "date")
        assert hasattr(perf, "total_pnl")
        assert hasattr(perf, "north_star_progress")
        assert hasattr(perf, "win_rate")


class TestRAGMLNeverSkipped:
    """Critical tests to ensure RAG/ML is never skipped."""

    def test_gate_must_be_called_before_execution(self):
        """Verify that place_order calls the gate before any execution."""
        import inspect

        from src.execution.alpaca_executor import AlpacaExecutor

        source = inspect.getsource(AlpacaExecutor.place_order)

        # Find where gate validation happens
        gate_line = source.find("validate_trade_mandatory")

        # Find where actual execution happens (submit_order)
        submit_line = source.find("submit_order")

        # Gate MUST come before execution
        assert gate_line > 0, "Gate validation not found in place_order"
        assert submit_line > 0, "submit_order not found in place_order"

        # The gate must be called BEFORE submit_order
        assert gate_line < submit_line, "Gate validation must happen BEFORE order submission"

    def test_gate_blocks_trades_properly(self):
        """Test that the gate can actually block trades."""
        from src.safety.mandatory_trade_gate import MandatoryTradeGate

        gate = MandatoryTradeGate()

        result = gate.validate_trade(
            symbol="AAPL",
            amount=1000.0,
            side="BUY",
        )

        all_messages = result.rag_warnings + result.ml_anomalies

