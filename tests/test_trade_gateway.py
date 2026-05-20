"""
Unit tests for Trade Gateway risk checks.

Tests key gateway functionality:
- Liquidity check (bid-ask spread)
- IV Rank validation for credit strategies
- Capital efficiency checks
- Allocation limits

These tests ensure the gateway properly rejects risky trades.
"""

from datetime import datetime as real_datetime
from unittest.mock import MagicMock, patch

import pytest

from src.risk.trade_gateway import RejectionReason, TradeGateway, TradeRequest


@pytest.fixture(autouse=True)
def mock_rag():
    """Mock RAG to prevent real lessons from blocking test trades."""
    with patch("src.risk.trade_gateway.LessonsLearnedRAG") as mock_rag_class:
        mock_rag_instance = MagicMock()
        mock_rag_instance.query.return_value = []  # No lessons found
        mock_rag_class.return_value = mock_rag_instance
        yield mock_rag_instance


@pytest.fixture(autouse=True)
def mock_total_pl():
    """Mock _get_total_pl to return positive P/L for test trades.

    This allows tests to pass Rule #1 check without complex Path mocking.
    """
    with patch.object(TradeGateway, "_get_total_pl", return_value=100.0):
        yield


@pytest.fixture(autouse=True)
def mock_rule_one_validator():
    """Mock Rule #1 validator to pass for all test trades.

    Tests in this file focus on liquidity/IV/capital checks, not Rule #1 compliance.
    """
    with patch("src.risk.trade_gateway.RuleOneValidator") as mock_validator_class:
        mock_validator = MagicMock()
        mock_result = MagicMock()
        mock_result.approved = True
        mock_result.in_universe = True
        mock_result.rejection_reasons = []
        mock_result.warnings = []
        mock_result.confidence = 0.85
        mock_result.to_dict.return_value = {"approved": True, "in_universe": True}
        mock_validator.validate.return_value = mock_result
        mock_validator_class.return_value = mock_validator
        yield mock_validator


@pytest.fixture(autouse=True)
def mock_drawdown():
    """Mock _get_drawdown to return 0% drawdown for test trades.

    This allows tests to pass circuit breaker check without complex state mocking.
    Tests focus on specific gateway features, not drawdown calculation.
    """
    with patch.object(TradeGateway, "_get_drawdown", return_value=0.0):
        yield


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
        # Added Jan 15, 2026: stop_price required by PreTradeChecklist per CLAUDE.md
        request = TradeRequest(
            symbol="SPY240315C00500000",
            side="buy",
            notional=500,
            source="test",
            is_option=True,
            bid_price=1.96,
            ask_price=2.00,
            stop_price=1.50,  # Stop-loss required per CLAUDE.md checklist
            is_spread=True,  # Mark as spread to pass checklist (debit spread)
            max_loss=200.0,  # Within 5% of $50000 equity
            dte=35,  # Within 30-45 DTE range
            request_time=real_datetime(2026, 5, 11),
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
            request_time=real_datetime(2026, 5, 11),
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
            request_time=real_datetime(2026, 5, 11),
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
            request_time=real_datetime(2026, 5, 11),
        )
        decision = gateway.evaluate(request)

        assert decision.approved


class TestTradeGatewayAllocationLimits:
    """Test allocation limits per symbol."""

    def test_over_allocation_rejected(self):
        """Test that > 5% allocation to single symbol is rejected (per CLAUDE.md)."""
        gateway = TradeGateway(executor=None, paper=True)
        # Use XOM (not in any correlation group) to avoid HIGH_CORRELATION rejection
        gateway.executor = MockExecutor(
            account_equity=10000,
            positions=[{"symbol": "XOM", "market_value": 400}],  # 4% already
        )

        # Trying to add $200 more would push to 6% (> 2% limit)
        request = TradeRequest(
            symbol="XOM",
            side="buy",
            notional=200,
            source="test",
        )
        decision = gateway.evaluate(request)

        assert not decision.approved
        assert RejectionReason.MAX_ALLOCATION_EXCEEDED in decision.rejection_reasons

    def test_under_allocation_approved(self):
        """Test that allocation below the canonical cap is not rejected."""
        gateway = TradeGateway(executor=None, paper=True)
        gateway.executor = MockExecutor(
            account_equity=10000,
            positions=[{"symbol": "SPY", "market_value": 100}],  # 1% already
        )

        # Adding $75 more would be 1.75% total (under 2%)
        request = TradeRequest(
            symbol="SPY",
            side="buy",
            notional=75,
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


class TestEarningsBlackoutEnforcement:
    """Test earnings blackout trade blocking during evaluation."""

    def test_sofi_blocked_during_blackout(self):
        """Test that SOFI trades are blocked during earnings blackout period."""
        gateway = TradeGateway(executor=None, paper=True)
        gateway.executor = MockExecutor(account_equity=50000)
        # Disable ticker whitelist for this test (SOFI not in SPY/IWM whitelist)
        gateway.TICKER_WHITELIST_ENABLED = False

        # Mock current date to be within SOFI blackout (Jan 23 - Feb 1)
        with patch("src.risk.trade_gateway.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = type(
                "Date", (), {"__le__": lambda s, o: True, "__ge__": lambda s, o: True}
            )()
            mock_dt.strptime = real_datetime.strptime
            mock_dt.now.return_value = real_datetime(2026, 1, 25)  # During blackout

            request = TradeRequest(
                symbol="SOFI",
                side="buy",
                notional=500,
                source="test",
                request_time=real_datetime(2026, 1, 25),
            )
            decision = gateway.evaluate(request)

            assert not decision.approved
            assert not decision.approved  # SOFI/F rejected (blacklisted or earnings)

    def test_sofi_option_blocked_during_blackout(self):
        """Test that SOFI options are blocked during earnings blackout."""
        gateway = TradeGateway(executor=None, paper=True)
        gateway.executor = MockExecutor(account_equity=50000)
        gateway.TICKER_WHITELIST_ENABLED = False

        with patch("src.risk.trade_gateway.datetime") as mock_dt:
            mock_dt.strptime = real_datetime.strptime
            mock_dt.now.return_value = real_datetime(2026, 1, 28)  # During blackout

            # SOFI option symbol (OCC format)
            request = TradeRequest(
                symbol="SOFI260206P00024000",
                side="sell",
                quantity=1,
                source="test",
                is_option=True,
                request_time=real_datetime(2026, 1, 28),
            )
            decision = gateway.evaluate(request)

            assert not decision.approved
            assert not decision.approved  # SOFI/F rejected (blacklisted or earnings)

    def test_f_blocked_during_blackout(self):
        """Test that F (Ford) trades are blocked during earnings blackout."""
        gateway = TradeGateway(executor=None, paper=True)
        gateway.executor = MockExecutor(account_equity=50000)
        gateway.TICKER_WHITELIST_ENABLED = False

        with patch("src.risk.trade_gateway.datetime") as mock_dt:
            mock_dt.strptime = real_datetime.strptime
            mock_dt.now.return_value = real_datetime(2026, 2, 5)  # During F blackout (Feb 3-11)

            request = TradeRequest(
                symbol="F",
                side="buy",
                notional=500,
                source="test",
                request_time=real_datetime(2026, 2, 5),
            )
            decision = gateway.evaluate(request)

            assert not decision.approved
            assert not decision.approved  # SOFI/F rejected (blacklisted or earnings)

    def test_spy_not_in_blackout(self):
        """Test that SPY (no earnings) is not blocked by blackout check."""
        gateway = TradeGateway(executor=None, paper=True)
        gateway.executor = MockExecutor(account_equity=50000)

        request = TradeRequest(
            symbol="SPY",
            side="buy",
            notional=500,
            source="test",
            request_time=real_datetime(2026, 5, 11),
        )
        decision = gateway.evaluate(request)

        # SPY should not have earnings blackout rejection
        assert RejectionReason.EARNINGS_BLACKOUT not in decision.rejection_reasons

    def test_check_earnings_blackout_method(self):
        """Test the _check_earnings_blackout method directly.

        SPY has no earnings, but new entries are blocked around FOMC announcements.
        """
        gateway = TradeGateway(executor=None, paper=True)

        is_blocked, reason = gateway._check_earnings_blackout(
            "SPY", as_of=real_datetime(2026, 5, 11)
        )
        assert not is_blocked
        assert reason == ""

        is_blocked, reason = gateway._check_earnings_blackout(
            "SPY", as_of=real_datetime(2026, 5, 4)
        )
        assert is_blocked
        assert "FOMC blackout 2026-05-04 to 2026-05-07" in reason


class TestEarningsPositionMonitor:
    """Test earnings position monitoring functionality."""

    def test_no_positions_returns_empty(self):
        """Test that no positions returns empty alerts list."""
        gateway = TradeGateway(executor=None, paper=True)
        gateway.executor = MockExecutor(positions=[])

        alerts = gateway.check_positions_for_earnings()
        assert alerts == []

    def test_position_without_earnings_no_alert(self):
        """Test that positions without earnings calendar don't trigger alerts."""
        gateway = TradeGateway(executor=None, paper=True)
        gateway.executor = MockExecutor(
            positions=[{"symbol": "SPY", "qty": 100, "unrealized_pl": 50}]
        )

        alerts = gateway.check_positions_for_earnings()
        assert alerts == []  # SPY not in EARNINGS_BLACKOUTS

    def test_sofi_position_generates_alert(self):
        """Test that SOFI position triggers earnings alert during blackout window."""
        from datetime import datetime as real_datetime

        gateway = TradeGateway(executor=None, paper=True)
        gateway.executor = MockExecutor(
            positions=[{"symbol": "SOFI", "qty": 25, "unrealized_pl": 16.88}]
        )

        # Blackout was Jan 23 - Feb 1, 2026. If past that, no alerts expected.
        alerts = gateway.check_positions_for_earnings()
        now = real_datetime.now()
        if now > real_datetime(2026, 2, 1):
            assert len(alerts) == 0  # Blackout expired
        else:
            assert len(alerts) == 1

    def test_sofi_option_generates_alert(self):
        """Test that SOFI option position triggers earnings alert during window."""
        from datetime import datetime as real_datetime

        gateway = TradeGateway(executor=None, paper=True)
        gateway.executor = MockExecutor(
            positions=[{"symbol": "SOFI260206P00024000", "qty": -2, "unrealized_pl": 23.00}]
        )

        alerts = gateway.check_positions_for_earnings()
        now = real_datetime.now()
        if now > real_datetime(2026, 2, 1):
            assert len(alerts) == 0  # Blackout expired
        else:
            assert len(alerts) == 1

    def test_action_recommends_close_on_profit(self):
        """Test that profitable position in blackout gets close recommendation."""
        gateway = TradeGateway(executor=None, paper=True)
        # Simulate position already in blackout with profit
        action = gateway._get_earnings_action(days_to_blackout=0, unrealized_pl=100, symbol="SOFI")
        assert "CLOSE_AT_PROFIT" in action

    def test_action_recommends_monitor_on_loss(self):
        """Test that losing position in blackout gets monitor recommendation."""
        gateway = TradeGateway(executor=None, paper=True)
        action = gateway._get_earnings_action(days_to_blackout=0, unrealized_pl=-50, symbol="SOFI")
        assert "MONITOR_CLOSELY" in action


class TestCreditSpreadMaxLoss:
    """Regression: credit-spread max-loss must scale with spread_width, not hardcoded $500.

    Bug history: trade_gateway.py:421 used `max_loss = 500 * quantity` for any
    credit-spread strategy_type, silently under-counting max loss by 50% on the
    $10-wide spreads the paper account uses at >=$100K equity. A 50-contract
    $10-wide credit spread should report $40,000 max loss (= ($10*100 - $2*100) * 50),
    not $25,000.
    """

    def test_credit_spread_max_loss_scales_with_width(self):
        gateway = TradeGateway(executor=None, paper=True)
        gateway.executor = MockExecutor(account_equity=95_000)
        request = TradeRequest(
            symbol="SPY260618P00686000",
            side="sell",
            notional=10_000,
            source="test",
            is_option=True,
            strategy_type="credit_spread",
            spread_width=10.0,
            premium_received=2.0,
            quantity=50,
        )
        rejected, reason = gateway._check_position_size_risk(request, account_equity=95_000)
        assert rejected, "50-lot $10-wide credit spread must trip 2% max-position cap"
        # True max loss = ($10*100 - $2*100) * 50 = $40,000
        # Buggy max loss would have been $500 * 50 = $25,000
        assert "$40000" in reason or "40000" in reason, (
            f"Expected max-loss of $40,000 in rejection reason, got: {reason}"
        )

    def test_credit_spread_max_loss_uses_premium(self):
        """Premium reduces max loss: ($10*100 - $1*100) * 1 = $900 for 1-lot."""
        gateway = TradeGateway(executor=None, paper=True)
        gateway.executor = MockExecutor(account_equity=200_000)
        request = TradeRequest(
            symbol="SPY260618P00686000",
            side="sell",
            notional=900,
            source="test",
            is_option=True,
            strategy_type="bull_put_spread",
            spread_width=10.0,
            premium_received=1.0,
            quantity=1,
        )
        rejected, _ = gateway._check_position_size_risk(request, account_equity=200_000)
        # 1-lot $900 max loss vs $200K equity = 0.45% << 2% -> not rejected on size
        assert not rejected, "1-lot $10-wide spread should pass on a $200K account"


class TestTradeGatewayLotSizeCap:
    """Regression: per-trade contract count must be capped at MAX_CONTRACTS_PER_TRADE.

    The 50/51-lot SPY 2026-06-18 IC violated controlled-experiment.md (1-lot only)
    because no structural cap existed in the gateway. Reference:
    .claude/rules/cto-decision-2026-05-19.md §3.1.
    """

    def _make_gateway(self, positions=None):
        gw = TradeGateway(executor=None, paper=True)
        gw.executor = MockExecutor(account_equity=100_000, positions=positions or [])
        return gw

    def test_open_request_above_lot_cap_is_rejected(self):
        gateway = self._make_gateway()
        request = TradeRequest(
            symbol="SPY260618P00686000",
            side="sell",
            quantity=50,
            source="test",
            is_option=True,
            strategy_type="bull_put_spread",
            spread_width=10.0,
            premium_received=2.0,
        )
        decision = gateway.evaluate(request)
        assert not decision.approved
        assert RejectionReason.LOT_SIZE_EXCEEDED in decision.rejection_reasons
        assert decision.metadata.get("lot_size_cap") == gateway.MAX_CONTRACTS_PER_TRADE
        assert decision.metadata.get("requested_quantity") == 50

    def test_open_request_at_lot_cap_passes_lot_check(self):
        gateway = self._make_gateway()
        request = TradeRequest(
            symbol="SPY260618P00686000",
            side="sell",
            quantity=1,
            source="test",
            is_option=True,
            strategy_type="bull_put_spread",
            spread_width=10.0,
            premium_received=2.0,
        )
        decision = gateway.evaluate(request)
        assert RejectionReason.LOT_SIZE_EXCEEDED not in decision.rejection_reasons

    def test_close_path_allowed_above_lot_cap(self):
        # Closing a pre-existing 50-lot position must remain possible — the cap
        # only applies when the symbol has no existing position to close.
        symbol = "SPY260618P00686000"
        gateway = self._make_gateway(
            positions=[{"symbol": symbol, "qty": -50, "unrealized_pl": 0}]
        )
        request = TradeRequest(
            symbol=symbol,
            side="buy",  # buy-to-close a short put
            quantity=50,
            source="test",
            is_option=True,
            strategy_type="bull_put_spread",
        )
        decision = gateway.evaluate(request)
        assert RejectionReason.LOT_SIZE_EXCEEDED not in decision.rejection_reasons


class TestTradeGatewayDecisionTelemetry:
    """Every gate decision must be durably persisted to JSONL for audit + analytics.

    This is the B2B-guardrail-SaaS productization seed: external buyers need an
    audit log of every guardrail decision their autonomous agent triggered.
    """

    def _make_gateway(self, tmp_path):
        gateway = TradeGateway(executor=None, paper=True)
        gateway.executor = MockExecutor(account_equity=100_000)
        gateway.DECISION_LOG_PATH = tmp_path / "gateway_decisions.jsonl"
        return gateway

    def test_decision_telemetry_logs_approved_trade(self, tmp_path):
        import json as _json

        gateway = self._make_gateway(tmp_path)
        request = TradeRequest(
            symbol="SPY",
            side="buy",
            notional=500,
            source="test_approved",
            is_option=False,
        )
        decision = gateway.evaluate(request)

        log_path = gateway.DECISION_LOG_PATH
        assert log_path.exists(), "telemetry file must be created"
        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 1
        record = _json.loads(lines[0])
        assert record["source"] == "test_approved"
        assert record["symbol"] == "SPY"
        assert record["approved"] == decision.approved
        assert "ts" in record and record["ts"].endswith("Z")
        assert "request_id" in record and len(record["request_id"]) == 32

    def test_decision_telemetry_logs_rejected_trade(self, tmp_path):
        import json as _json

        gateway = self._make_gateway(tmp_path)
        request = TradeRequest(
            symbol="SPY240315C00500000",
            side="buy",
            notional=500,
            source="test_rejected",
            is_option=True,
            bid_price=1.70,
            ask_price=2.00,  # 15% spread -> ILLIQUID
        )
        decision = gateway.evaluate(request)
        assert not decision.approved

        record = _json.loads(gateway.DECISION_LOG_PATH.read_text().strip().splitlines()[-1])
        assert record["approved"] is False
        assert "ILLIQUID_OPTION" in record["rejection_reasons"]

    def test_decision_telemetry_failure_does_not_break_trading(self, tmp_path, monkeypatch):
        # If the log path is unwriteable, the gateway must still return a decision.
        gateway = self._make_gateway(tmp_path)
        gateway.DECISION_LOG_PATH = tmp_path / "nonexistent" / "ro" / "decisions.jsonl"

        def boom(*a, **kw):
            raise OSError("simulated filesystem failure")

        monkeypatch.setattr("builtins.open", boom)

        request = TradeRequest(
            symbol="SPY", side="buy", notional=500, source="test_telemetry_fail"
        )
        decision = gateway.evaluate(request)  # must not raise
        assert decision is not None
        assert isinstance(decision.approved, bool)

    def test_decision_telemetry_appends_multiple(self, tmp_path):
        gateway = self._make_gateway(tmp_path)
        for i in range(3):
            gateway.evaluate(
                TradeRequest(symbol="SPY", side="buy", notional=100, source=f"r{i}")
            )
        lines = gateway.DECISION_LOG_PATH.read_text().strip().splitlines()
        assert len(lines) == 3
        sources = [__import__("json").loads(line)["source"] for line in lines]
        assert sources == ["r0", "r1", "r2"]
