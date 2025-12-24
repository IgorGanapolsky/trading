"""
Unit tests for Trade Gateway risk checks.

Tests key gateway functionality:
- Liquidity check (bid-ask spread)
- IV Rank validation for credit strategies
- Capital efficiency checks
- Allocation limits

These tests ensure the gateway properly rejects risky trades.
"""

from src.risk.trade_gateway import RejectionReason, TradeGateway, TradeRequest


class MockExecutor:
    """Mock executor for testing."""

    def __init__(self, account_equity: float = 100000, positions: list = None):
        self.account_equity = account_equity
        self._positions = positions or []

    def get_positions(self):
        return self._positions


class TestTradeGatewayLiquidityCheck:
    """Test liquidity check for options (bid-ask spread validation)."""

    def test_illiquid_option_rejected_with_wide_spread(self):
        """Test that options with bid-ask spread > 5% are rejected."""
        gateway = TradeGateway(executor=None, paper=True)
        gateway.executor = MockExecutor(account_equity=50000)

        # 15% spread = (2.00 - 1.70) / 2.00 = 0.15
        request = TradeRequest(
            symbol="SPY240315C00500000",
            side="buy",
            notional=500,
            source="test",
            is_option=True,
            bid_price=1.70,
            ask_price=2.00,
        )
        decision = gateway.evaluate(request)

        assert not decision.approved
        assert RejectionReason.ILLIQUID_OPTION in decision.rejection_reasons

    def test_liquid_option_approved_with_tight_spread(self):
        """Test that options with bid-ask spread < 5% are approved."""
        gateway = TradeGateway(executor=None, paper=True)
        gateway.executor = MockExecutor(account_equity=50000)

        # 2% spread = (2.00 - 1.96) / 2.00 = 0.02
        request = TradeRequest(
            symbol="SPY240315C00500000",
            side="buy",
            notional=500,
            source="test",
            is_option=True,
            bid_price=1.96,
            ask_price=2.00,
        )
        decision = gateway.evaluate(request)

        assert decision.approved

    def test_equity_trade_bypasses_liquidity_check(self):
        """Test that non-option trades skip liquidity check."""
        gateway = TradeGateway(executor=None, paper=True)
        gateway.executor = MockExecutor(account_equity=50000)

        request = TradeRequest(
            symbol="SPY",
            side="buy",
            notional=500,
            source="test",
            is_option=False,
        )
        decision = gateway.evaluate(request)

        # Should pass (no liquidity rejection for equities)
        assert RejectionReason.ILLIQUID_OPTION not in decision.rejection_reasons


class TestTradeGatewayIVRankCheck:
    """Test IV Rank validation for credit strategies."""

    def test_low_iv_rejects_credit_strategy(self):
        """Test that IV Rank < 20 rejects credit strategies."""
        gateway = TradeGateway(executor=None, paper=True)
        gateway.executor = MockExecutor(account_equity=50000)

        request = TradeRequest(
            symbol="SPY",
            side="buy",
            notional=500,
            source="test",
            strategy_type="iron_condor",
            iv_rank=15.0,
        )
        decision = gateway.evaluate(request)

        assert not decision.approved
        assert RejectionReason.IV_RANK_TOO_LOW in decision.rejection_reasons

    def test_high_iv_approves_credit_strategy(self):
        """Test that IV Rank >= 20 allows credit strategies."""
        gateway = TradeGateway(executor=None, paper=True)
        gateway.executor = MockExecutor(account_equity=50000)

        request = TradeRequest(
            symbol="SPY",
            side="buy",
            notional=500,
            source="test",
            strategy_type="iron_condor",
            iv_rank=60.0,
        )
        decision = gateway.evaluate(request)

        assert decision.approved


class TestTradeGatewayCapitalEfficiency:
    """Test capital efficiency checks."""

    def test_small_account_rejects_iron_condor(self):
        """Test that $5k account cannot trade iron condors (need $10k)."""
        gateway = TradeGateway(executor=None, paper=True)
        gateway.executor = MockExecutor(account_equity=5000)

        request = TradeRequest(
            symbol="SPY",
            side="buy",
            notional=500,
            source="test",
            strategy_type="iron_condor",
            iv_rank=50.0,
        )
        decision = gateway.evaluate(request)

        assert not decision.approved
        assert RejectionReason.CAPITAL_INEFFICIENT in decision.rejection_reasons

    def test_adequate_capital_allows_iron_condor(self):
        """Test that $50k account can trade iron condors."""
        gateway = TradeGateway(executor=None, paper=True)
        gateway.executor = MockExecutor(account_equity=50000)

        request = TradeRequest(
            symbol="SPY",
            side="buy",
            notional=500,
            source="test",
            strategy_type="iron_condor",
            iv_rank=50.0,
        )
        decision = gateway.evaluate(request)

        assert decision.approved


class TestTradeGatewayAllocationLimits:
    """Test allocation limits per symbol."""

    def test_over_allocation_rejected(self):
        """Test that > 15% allocation to single symbol is rejected."""
        gateway = TradeGateway(executor=None, paper=True)
        # Use AAPL (not in any correlation group) to avoid HIGH_CORRELATION rejection
        gateway.executor = MockExecutor(
            account_equity=10000,
            positions=[{"symbol": "AAPL", "market_value": 1400}],  # 14% already
        )

        # Trying to add $200 more would push to 16%
        request = TradeRequest(
            symbol="AAPL",
            side="buy",
            notional=200,
            source="test",
        )
        decision = gateway.evaluate(request)

        assert not decision.approved
        assert RejectionReason.MAX_ALLOCATION_EXCEEDED in decision.rejection_reasons

    def test_under_allocation_approved(self):
        """Test that < 15% allocation is approved."""
        gateway = TradeGateway(executor=None, paper=True)
        gateway.executor = MockExecutor(
            account_equity=10000,
            positions=[{"symbol": "TSLA", "market_value": 500}],  # 5% already
        )

        # Adding $500 more would be 10% total (under 15%)
        request = TradeRequest(
            symbol="TSLA",
            side="buy",
            notional=500,
            source="test",
        )
        decision = gateway.evaluate(request)

        # Should not be rejected for allocation (may have other checks)
        assert RejectionReason.MAX_ALLOCATION_EXCEEDED not in decision.rejection_reasons


class TestTradeGatewaySuicideCommand:
    """Test suicide command protection ($1M+ trades)."""

    def test_suicide_command_rejected(self):
        """Test that massive trades are rejected for multiple reasons."""
        gateway = TradeGateway(executor=None, paper=True)

        request = TradeRequest(
            symbol="AMC",
            side="buy",
            notional=1000000,
            source="test",
        )
        decision = gateway.evaluate(request)

        assert not decision.approved
        # Should fail for insufficient funds AND over-allocation
        assert RejectionReason.INSUFFICIENT_FUNDS in decision.rejection_reasons
        assert RejectionReason.MAX_ALLOCATION_EXCEEDED in decision.rejection_reasons
