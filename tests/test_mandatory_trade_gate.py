"""Tests for mandatory_trade_gate.py - Critical trade validation."""


class TestGateResult:
    """Test GateResult dataclass."""

    def test_gate_result_creation(self):
        """Test creating GateResult with all fields."""
        from src.safety.mandatory_trade_gate import GateResult

        result = GateResult(
            approved=True,
            reason="Trade approved",
            rag_warnings=["warning1"],
            ml_anomalies=["anomaly1"],
            confidence=0.95,
        )
        assert result.approved is True
        assert result.reason == "Trade approved"
        assert len(result.rag_warnings) == 1
        assert result.confidence == 0.95

    def test_gate_result_defaults(self):
        """Test GateResult default values."""
        from src.safety.mandatory_trade_gate import GateResult

        result = GateResult(approved=False)
        assert result.approved is False
        assert result.reason == ""
        assert result.rag_warnings == []
        assert result.ml_anomalies == []
        assert result.confidence == 1.0


class TestValidateTradeMandatory:
    """Test validate_trade_mandatory function."""

    def test_valid_trade_approved(self):
        """Test that valid trade is approved (within 10% position limit)."""
        from src.safety.mandatory_trade_gate import validate_trade_mandatory

        # Trade must be <10% of equity to pass
        result = validate_trade_mandatory(
            symbol="SPY",
            amount=400.0,  # 8% of 5000 - within 10% limit
            side="BUY",
            strategy="CSP",
            context={"equity": 5000.0},
        )
        assert result.approved is True
        assert "approved" in result.reason.lower()

    def test_position_too_large_rejected(self):
        """Test that position >10% of equity is rejected."""
        from src.safety.mandatory_trade_gate import validate_trade_mandatory

        result = validate_trade_mandatory(
            symbol="SPY",
            amount=1000.0,  # 20% of 5000 - exceeds 10% limit
            side="BUY",
            strategy="CSP",
            context={"equity": 5000.0},
        )
        assert result.approved is False
        assert "exceeds" in result.reason.lower() or "max" in result.reason.lower()

    def test_invalid_amount_rejected(self):
        """Test that below minimum amount is rejected."""
        from src.safety.mandatory_trade_gate import validate_trade_mandatory

        result = validate_trade_mandatory(
            symbol="SPY",
            amount=0.5,  # Below $1 minimum
            side="BUY",
            strategy="CSP",
        )
        assert result.approved is False
        assert "minimum" in result.reason.lower() or "below" in result.reason.lower()

    def test_invalid_side_rejected(self):
        """Test that invalid side is rejected."""
        from src.safety.mandatory_trade_gate import validate_trade_mandatory

        result = validate_trade_mandatory(
            symbol="SPY",
            amount=1000.0,
            side="INVALID",
            strategy="CSP",
        )
        assert result.approved is False
        assert "invalid trade side" in result.reason.lower()

    def test_zero_equity_rejected(self):
        """Test that trading with zero equity is rejected (ll_051)."""
        from src.safety.mandatory_trade_gate import validate_trade_mandatory

        result = validate_trade_mandatory(
            symbol="SPY",
            amount=1000.0,
            side="BUY",
            strategy="CSP",
            context={"equity": 0},
        )
        assert result.approved is False
        assert "blind trading" in result.reason.lower()
        assert any("ll_051" in w for w in result.rag_warnings)


class TestTradeBlockedError:
    """Test TradeBlockedError exception."""

    def test_exception_stores_gate_result(self):
        """Test that exception stores the gate result."""
        from src.safety.mandatory_trade_gate import GateResult, TradeBlockedError

        gate_result = GateResult(approved=False, reason="Test block")
        error = TradeBlockedError(gate_result)
        assert error.gate_result is gate_result
        assert "Test block" in str(error)
