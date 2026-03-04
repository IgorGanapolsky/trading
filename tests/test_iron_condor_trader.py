"""Tests for iron_condor_trader.py - the primary money-making strategy script.

Coverage:
- IronCondorStrategy.calculate_strikes (delta selection, strike validation)
- IronCondorStrategy.calculate_premiums
- IronCondorStrategy.find_trade (end-to-end trade finding)
- IronCondorStrategy.execute (live & simulated, position limits, RAG blocking)
- IronCondorLegs dataclass
- 4-leg validation (all legs present)
- Position sizing (5% limit via config)
- Error handling (API failures, credential failures, position check failures)

All Alpaca API calls are mocked. No real API calls.
"""

import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch


sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.iron_condor_trader import IronCondorLegs, IronCondorStrategy
from src.core.trading_constants import MAX_POSITIONS


class TestIronCondorLegs:
    """Test the IronCondorLegs dataclass."""

    def test_legs_dataclass_creation(self):
        """All fields should be populated correctly."""
        legs = IronCondorLegs(
            underlying="SPY",
            expiry="2026-03-20",
            dte=30,
            short_put=650.0,
            long_put=640.0,
            short_call=720.0,
            long_call=730.0,
            credit_received=2.00,
            max_risk=800.0,
            max_profit=200.0,
        )
        assert legs.underlying == "SPY"
        assert legs.short_put == 650.0
        assert legs.long_put == 640.0
        assert legs.short_call == 720.0
        assert legs.long_call == 730.0
        assert legs.credit_received == 2.00
        assert legs.max_risk == 800.0
        assert legs.max_profit == 200.0
        assert legs.dte == 30

    def test_legs_has_all_four_legs(self):
        """Iron condor must have all 4 legs defined."""
        legs = IronCondorLegs(
            underlying="SPY",
            expiry="2026-03-20",
            dte=30,
            short_put=650.0,
            long_put=640.0,
            short_call=720.0,
            long_call=730.0,
            credit_received=2.00,
            max_risk=800.0,
            max_profit=200.0,
        )
        # All four legs must be non-zero
        assert legs.long_put > 0
        assert legs.short_put > 0
        assert legs.short_call > 0
        assert legs.long_call > 0
        # Long put < short put < short call < long call
        assert legs.long_put < legs.short_put
        assert legs.short_put < legs.short_call
        assert legs.short_call < legs.long_call


class TestCalculateStrikes:
    """Test strike calculation logic."""

    def test_strikes_for_spy_at_690(self):
        """Strike calculation at SPY ~690."""
        strategy = IronCondorStrategy()
        long_put, short_put, short_call, long_call = strategy.calculate_strikes(690.0)

        # Short put should be ~5% below price, rounded to $5
        assert short_put == round(690.0 * 0.95 / 5) * 5  # 655.5 -> 655
        assert long_put == short_put - 10  # $10 wing width

        # Short call should be ~5% above price, rounded to $5
        assert short_call == round(690.0 * 1.05 / 5) * 5  # 724.5 -> 725
        assert long_call == short_call + 10

    def test_strikes_rounded_to_5_dollar_increments(self):
        """SPY options only exist at $5 increments for OTM options."""
        strategy = IronCondorStrategy()
        long_put, short_put, short_call, long_call = strategy.calculate_strikes(593.0)

        # All strikes must be multiples of $5
        assert short_put % 5 == 0, f"Short put {short_put} is not a $5 multiple"
        assert long_put % 5 == 0, f"Long put {long_put} is not a $5 multiple"
        assert short_call % 5 == 0, f"Short call {short_call} is not a $5 multiple"
        assert long_call % 5 == 0, f"Long call {long_call} is not a $5 multiple"

    def test_wing_width_matches_config(self):
        """Wing width should match config (default $10)."""
        strategy = IronCondorStrategy()
        long_put, short_put, short_call, long_call = strategy.calculate_strikes(700.0)

        assert short_put - long_put == strategy.config["wing_width"]
        assert long_call - short_call == strategy.config["wing_width"]

    def test_strike_ordering(self):
        """Strikes must be ordered: LP < SP < SC < LC."""
        strategy = IronCondorStrategy()
        long_put, short_put, short_call, long_call = strategy.calculate_strikes(700.0)

        assert long_put < short_put < short_call < long_call


class TestCalculatePremiums:
    """Test premium calculation."""

    def test_premium_structure(self):
        """Premiums should have correct structure and values."""
        strategy = IronCondorStrategy()
        legs = (640.0, 650.0, 720.0, 730.0)
        premiums = strategy.calculate_premiums(legs, 30)

        assert "credit" in premiums
        assert "max_risk" in premiums
        assert "max_profit" in premiums
        assert "risk_reward" in premiums
        assert premiums["credit"] > 0
        assert premiums["max_risk"] > 0
        assert premiums["max_profit"] > 0

    def test_max_risk_calculation(self):
        """Max risk = wing_width * 100 - credit * 100."""
        strategy = IronCondorStrategy()
        legs = (640.0, 650.0, 720.0, 730.0)
        premiums = strategy.calculate_premiums(legs, 30)

        wing_width = strategy.config["wing_width"]
        expected_max_risk = (wing_width * 100) - (premiums["credit"] * 100)
        assert premiums["max_risk"] == expected_max_risk


class TestStrategyConfig:
    """Test strategy configuration matches CLAUDE.md mandates."""

    def test_underlying_is_spy(self):
        """Per CLAUDE.md: SPY ONLY."""
        strategy = IronCondorStrategy()
        assert strategy.config["underlying"] == "SPY"

    def test_position_size_is_5_percent(self):
        """Per CLAUDE.md: 5% of portfolio per position."""
        strategy = IronCondorStrategy()
        assert strategy.config["position_size_pct"] == 0.05

    def test_max_positions_derived_from_canonical_leg_limit(self):
        """Max iron-condor count is derived from canonical option-leg budget."""
        strategy = IronCondorStrategy()
        assert strategy.config["max_positions"] == max(1, int(MAX_POSITIONS) // 4)

    def test_exit_dte_is_7(self):
        """Per LL-268: Exit at 7 DTE."""
        strategy = IronCondorStrategy()
        assert strategy.config["exit_dte"] == 7

    def test_wing_width_is_10(self):
        """Per CLAUDE.md: $10-wide wings."""
        strategy = IronCondorStrategy()
        assert strategy.config["wing_width"] == 10


class TestFindTrade:
    """Test find_trade method."""

    @patch.object(IronCondorStrategy, "get_underlying_price", return_value=690.0)
    def test_find_trade_returns_iron_condor_legs(self, mock_price):
        """find_trade should return a complete IronCondorLegs object."""
        strategy = IronCondorStrategy()
        ic = strategy.find_trade()

        assert ic is not None
        assert isinstance(ic, IronCondorLegs)
        assert ic.underlying == "SPY"
        assert ic.long_put < ic.short_put < ic.short_call < ic.long_call
        assert ic.credit_received > 0
        assert ic.max_risk > 0
        assert ic.max_profit > 0

    @patch.object(IronCondorStrategy, "get_underlying_price", return_value=690.0)
    def test_find_trade_expiry_is_friday(self, mock_price):
        """Options expiry should be a Friday."""
        strategy = IronCondorStrategy()
        ic = strategy.find_trade()

        expiry_date = datetime.strptime(ic.expiry, "%Y-%m-%d")
        assert expiry_date.weekday() == 4, f"Expiry {ic.expiry} is not a Friday"


class TestExecute:
    """Test iron condor execution (both live and simulated)."""

    def _make_ic(self):
        """Helper to create a test IronCondorLegs."""
        return IronCondorLegs(
            underlying="SPY",
            expiry="2026-03-20",
            dte=30,
            short_put=655.0,
            long_put=645.0,
            short_call=725.0,
            long_call=735.0,
            credit_received=2.00,
            max_risk=800.0,
            max_profit=200.0,
        )

    @patch("scripts.iron_condor_trader.LessonsLearnedRAG")
    def test_execute_simulated_mode(self, mock_rag_class):
        """Simulated execution should return SIMULATED status."""
        mock_rag = MagicMock()
        mock_rag.search.return_value = []
        mock_rag_class.return_value = mock_rag

        strategy = IronCondorStrategy()
        ic = self._make_ic()

        with patch.object(strategy, "_record_trade"):
            trade = strategy.execute(ic, live=False)

        assert trade["status"] == "SIMULATED"
        assert trade["strategy"] == "iron_condor"
        assert trade["underlying"] == "SPY"
        assert "legs" in trade
        assert trade["legs"]["long_put"] == 645.0
        assert trade["legs"]["short_put"] == 655.0
        assert trade["legs"]["short_call"] == 725.0
        assert trade["legs"]["long_call"] == 735.0

    @patch("scripts.iron_condor_trader.LessonsLearnedRAG")
    def test_execute_blocked_by_rag_critical_lesson(self, mock_rag_class):
        """Execution should be blocked by critical RAG lesson about iron condors."""

        @dataclass
        class FakeLesson:
            id: str
            title: str
            severity: str
            snippet: str
            prevention: str
            file: str

        critical_lesson = FakeLesson(
            id="LL-999",
            title="iron condor total loss",
            severity="CRITICAL",
            snippet="Lost everything on iron condor",
            prevention="Stop trading iron condors",
            file="test.md",
        )

        mock_rag = MagicMock()
        mock_rag.search.return_value = [(critical_lesson, 0.95)]
        mock_rag_class.return_value = mock_rag

        strategy = IronCondorStrategy()
        ic = self._make_ic()
        trade = strategy.execute(ic, live=False)

        assert trade["status"] == "BLOCKED_BY_RAG"
        assert "LL-999" in trade.get("lesson_id", "")

    @patch("scripts.iron_condor_trader.LessonsLearnedRAG")
    def test_execute_rag_resolved_lesson_not_blocking(self, mock_rag_class):
        """Resolved RAG lessons should not block execution."""

        @dataclass
        class FakeLesson:
            id: str
            title: str
            severity: str
            snippet: str
            prevention: str
            file: str

        resolved_lesson = FakeLesson(
            id="LL-100",
            title="iron condor partial fill resolved",
            severity="RESOLVED",
            snippet="Issue resolved with MLeg orders",
            prevention="Use MLeg orders",
            file="test.md",
        )

        mock_rag = MagicMock()
        mock_rag.search.return_value = [(resolved_lesson, 0.80)]
        mock_rag_class.return_value = mock_rag

        strategy = IronCondorStrategy()
        ic = self._make_ic()

        with patch.object(strategy, "_record_trade"):
            trade = strategy.execute(ic, live=False)

        assert trade["status"] == "SIMULATED"

    @patch("scripts.iron_condor_trader.LessonsLearnedRAG")
    def test_execute_live_position_limit_blocks(self, mock_rag_class):
        """Live execution should block when position limit is reached."""
        # Create 20 mock option positions (5 ICs = 20 contracts)
        mock_positions = []
        for i in range(20):
            pos = MagicMock()
            pos.symbol = f"SPY260320P0065{i:04d}"  # Option-like symbol
            pos.qty = "1"
            pos.avg_entry_price = "1.50"
            mock_positions.append(pos)

        mock_client = MagicMock()
        mock_client.get_all_positions.return_value = mock_positions

        mock_rag = MagicMock()
        mock_rag.search.return_value = []
        mock_rag_class.return_value = mock_rag

        strategy = IronCondorStrategy()
        ic = self._make_ic()

        with (
            patch("alpaca.trading.client.TradingClient", return_value=mock_client),
            patch(
                "src.utils.alpaca_client.get_alpaca_credentials",
                return_value=("test_key", "test_secret"),
            ),
        ):
            trade = strategy.execute(ic, live=True)

        assert trade["status"] == "SKIPPED_POSITION_LIMIT"

    @patch("scripts.iron_condor_trader.LessonsLearnedRAG")
    def test_execute_live_position_check_failure_blocks(self, mock_rag_class):
        """If position check fails, trade should be blocked (fail closed)."""
        mock_client = MagicMock()
        mock_client.get_all_positions.side_effect = Exception("API timeout")

        strategy = IronCondorStrategy()
        ic = self._make_ic()

        with (
            patch("alpaca.trading.client.TradingClient", return_value=mock_client),
            patch(
                "src.utils.alpaca_client.get_alpaca_credentials",
                return_value=("test_key", "test_secret"),
            ),
        ):
            trade = strategy.execute(ic, live=True)

        assert trade["status"] == "BLOCKED_POSITION_CHECK_FAILED"
        assert "API timeout" in trade["reason"]

    @patch("scripts.iron_condor_trader.LessonsLearnedRAG")
    def test_execute_live_no_credentials_blocks(self, mock_rag_class):
        """Live execution with no credentials should not submit orders."""
        mock_rag = MagicMock()
        mock_rag.search.return_value = []
        mock_rag_class.return_value = mock_rag

        strategy = IronCondorStrategy()
        ic = self._make_ic()

        with (
            patch(
                "src.utils.alpaca_client.get_alpaca_credentials",
                return_value=(None, None),
            ),
        ):
            with patch.object(strategy, "_record_trade"):
                trade = strategy.execute(ic, live=True)

        # Should still complete but not submit any orders
        assert trade["order_ids"] == []
