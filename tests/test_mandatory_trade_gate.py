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

        # Trade must be <5% of equity to pass (per CLAUDE.md)
        result = validate_trade_mandatory(
            symbol="SPY",
            amount=200.0,  # 4% of 5000 - within 5% limit
            side="BUY",
            strategy="CSP",
            context={"equity": 5000.0},
        )
        assert result.approved is True
        assert "approved" in result.reason.lower()

    def test_position_too_large_rejected(self):
        """Test that position >5% of equity is rejected (per CLAUDE.md)."""
        from src.safety.mandatory_trade_gate import validate_trade_mandatory

        result = validate_trade_mandatory(
            symbol="SPY",
            amount=300.0,  # 6% of 5000 - exceeds 5% limit
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

    def test_position_stacking_blocked(self):
        """Test that buying more of an existing symbol is blocked (LL-275).

        This is the fix for the 658 put disaster where 9 separate BUY orders
        accumulated 8 contracts because the gate didn't check for existing positions.
        """
        from src.safety.mandatory_trade_gate import validate_trade_mandatory

        # Simulate already holding SPY260220P00658000
        existing_positions = [
            {"symbol": "SPY260220P00658000", "qty": "2"},  # Already hold 2
        ]

        result = validate_trade_mandatory(
            symbol="SPY260220P00658000",  # Try to buy MORE of same symbol
            amount=100.0,
            side="BUY",
            strategy="iron_condor",
            context={"equity": 5000.0, "positions": existing_positions},
        )
        assert result.approved is False
        assert "stacking" in result.reason.lower() or "already hold" in result.reason.lower()
        assert "658000" in result.reason

    def test_sell_existing_position_allowed(self):
        """Test that SELLING an existing position is still allowed."""
        from src.safety.mandatory_trade_gate import validate_trade_mandatory

        existing_positions = [
            {"symbol": "SPY260220P00658000", "qty": "2"},
        ]

        result = validate_trade_mandatory(
            symbol="SPY260220P00658000",
            amount=100.0,
            side="SELL",  # Selling should be allowed
            strategy="iron_condor",
            context={"equity": 5000.0, "positions": existing_positions},
        )
        # SELL should not be blocked by stacking rule
        assert "stacking" not in result.reason.lower()


class TestTradeBlockedError:
    """Test TradeBlockedError exception."""

    def test_exception_stores_gate_result(self):
        """Test that exception stores the gate result."""
        from src.safety.mandatory_trade_gate import GateResult, TradeBlockedError

        gate_result = GateResult(approved=False, reason="Test block")
        error = TradeBlockedError(gate_result)
        assert error.gate_result is gate_result
        assert "Test block" in str(error)
