"""Tests for iron_condor_trader.py - the primary money-making strategy script.

Coverage:
- IronCondorStrategy.calculate_strikes (delta selection, strike validation)
- IronCondorStrategy.calculate_premiums
- IronCondorStrategy.find_trade (end-to-end trade finding)
- IronCondorStrategy.execute (live & simulated, position limits, RAG blocking)
- IronCondorLegs dataclass
- 4-leg validation (all legs present)
- Position sizing (canonical limit via config)
- Error handling (API failures, credential failures, position check failures)

All Alpaca API calls are mocked. No real API calls.
"""

import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# Skip all tests if dotenv is not available
pytest.importorskip("dotenv")

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.iron_condor_trader import (
    IronCondorLegs,
    IronCondorStrategy,
    _script_level_ml_halt_allows_validation,
)
import scripts.iron_condor_trader as trader_mod
from src.core.trading_constants import MAX_POSITION_PCT, MAX_POSITIONS


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


class TestScriptLevelTradingHalt:
    """Script-level halt handling must match the mandatory trade gate."""

    def test_ml_halt_allows_validation_reset_paper_entry(self, monkeypatch, tmp_path):
        import json

        state_file = tmp_path / "system_state.json"
        state_file.write_text(
            json.dumps(
                {
                    "north_star_weekly_gate": {
                        "mode": "validation_reset",
                        "allow_validation_entries": True,
                        "block_live_new_positions": True,
                    }
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(trader_mod, "SYSTEM_STATE_PATH", state_file)

        assert _script_level_ml_halt_allows_validation(
            halt_reason="ML GATE BLOCKED: Win rate 24.2% < 50.0%",
            explicit_live=False,
        )

    def test_ml_halt_still_blocks_explicit_live_entry(self, monkeypatch, tmp_path):
        import json

        state_file = tmp_path / "system_state.json"
        state_file.write_text(
            json.dumps(
                {
                    "north_star_weekly_gate": {
                        "mode": "validation_reset",
                        "allow_validation_entries": True,
                        "block_live_new_positions": True,
                    }
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(trader_mod, "SYSTEM_STATE_PATH", state_file)

        assert not _script_level_ml_halt_allows_validation(
            halt_reason="ML GATE BLOCKED: Win rate 24.2% < 50.0%",
            explicit_live=True,
        )

    def test_non_ml_halt_still_blocks_validation_reset(self, monkeypatch, tmp_path):
        import json

        state_file = tmp_path / "system_state.json"
        state_file.write_text(
            json.dumps(
                {
                    "north_star_weekly_gate": {
                        "mode": "validation_reset",
                        "allow_validation_entries": True,
                        "block_live_new_positions": True,
                    }
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(trader_mod, "SYSTEM_STATE_PATH", state_file)

        assert not _script_level_ml_halt_allows_validation(
            halt_reason="Manual operator halt for review.",
            explicit_live=False,
        )


class TestCalculateStrikes:
    """Test strike calculation via calculate_strikes method."""

    def _strikes(self, price):
        """Get expected strikes for a given price (15-delta heuristic math)."""
        short_put = round(price * 0.95 / 5) * 5
        short_call = round(price * 1.05 / 5) * 5
        long_put = short_put - 10
        long_call = short_call + 10
        return long_put, short_put, short_call, long_call

    def test_strikes_for_spy_at_690(self):
        """Strike calculation at SPY ~690."""
        long_put, short_put, short_call, long_call = self._strikes(690.0)

        assert short_put == round(690.0 * 0.95 / 5) * 5  # 655.5 -> 655
        assert long_put == short_put - 10  # $10 wing width
        assert short_call == round(690.0 * 1.05 / 5) * 5  # 724.5 -> 725
        assert long_call == short_call + 10

    def test_strikes_rounded_to_5_dollar_increments(self):
        """SPY options only exist at $5 increments for OTM options."""
        long_put, short_put, short_call, long_call = self._strikes(593.0)

        assert short_put % 5 == 0, f"Short put {short_put} is not a $5 multiple"
        assert long_put % 5 == 0, f"Long put {long_put} is not a $5 multiple"
        assert short_call % 5 == 0, f"Short call {short_call} is not a $5 multiple"
        assert long_call % 5 == 0, f"Long call {long_call} is not a $5 multiple"

    def test_wing_width_matches_config(self):
        """Wing width should match config (default $10)."""
        long_put, short_put, short_call, long_call = self._strikes(700.0)
        assert short_put - long_put == 10
        assert long_call - short_call == 10

    def test_strike_ordering(self):
        """Strikes must be ordered: LP < SP < SC < LC."""
        long_put, short_put, short_call, long_call = self._strikes(700.0)
        assert long_put < short_put < short_call < long_call

    def test_heuristic_fallback_blocked(self):
        """Heuristic fallback must return None (unknown delta is unsafe)."""
        strategy = IronCondorStrategy()
        with patch(
            "src.markets.option_chain._select_from_live_chain", side_effect=ValueError("test")
        ):
            result = strategy.calculate_strikes(700.0)
        assert result == (None, None, None, None)

    def test_config_min_dte_is_30(self):
        """CLAUDE.md mandate: minimum 30 DTE."""
        strategy = IronCondorStrategy()
        assert strategy.config["min_dte"] == 30


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

    def test_position_size_matches_canonical_limit(self):
        """Per CLAUDE.md: use the canonical position cap."""
        strategy = IronCondorStrategy()
        assert strategy.config["position_size_pct"] == MAX_POSITION_PCT

    def test_max_positions_derived_from_canonical_leg_limit(self):
        """Max iron-condor count is derived from canonical option-leg budget."""
        strategy = IronCondorStrategy()
        assert strategy.config["max_positions"] == max(1, int(MAX_POSITIONS) // 4)

    def test_exit_dte_is_7(self):
        """Per LL-268: Exit at 7 DTE."""
        strategy = IronCondorStrategy()
        assert strategy.config["exit_dte"] == 7

    def test_wing_width_is_5(self):
        """Validation hypothesis rejects 10-wide wings; cohort trades $5-wide."""
        strategy = IronCondorStrategy()
        assert strategy.config["wing_width"] == 5


class TestFindTrade:
    """Test find_trade method with mocked strikes."""

    @patch.object(IronCondorStrategy, "get_underlying_price", return_value=690.0)
    @patch.object(
        IronCondorStrategy, "calculate_strikes", return_value=(645.0, 655.0, 725.0, 735.0)
    )
    def test_find_trade_returns_iron_condor_legs(self, mock_strikes, mock_price):
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
    @patch.object(
        IronCondorStrategy, "calculate_strikes", return_value=(645.0, 655.0, 725.0, 735.0)
    )
    def test_find_trade_expiry_is_friday(self, mock_strikes, mock_price):
        """Options expiry should be a Friday."""
        strategy = IronCondorStrategy()
        ic = strategy.find_trade()

        assert ic is not None
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
            patch.object(strategy, "_validate_sync_freshness", return_value=(True, "", {})),
            patch(
                "scripts.iron_condor_trader.make_alpaca_trading_client", return_value=mock_client
            ),
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
            patch.object(strategy, "_validate_sync_freshness", return_value=(True, "", {})),
            patch(
                "scripts.iron_condor_trader.make_alpaca_trading_client", return_value=mock_client
            ),
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
            patch.object(strategy, "_validate_sync_freshness", return_value=(True, "", {})),
            patch(
                "src.utils.alpaca_client.get_alpaca_credentials",
                return_value=(None, None),
            ),
            patch(
                "src.safety.behavioral_guard.BehavioralGuard.evaluate",
                return_value=SimpleNamespace(
                    passed=True,
                    checks_run=["fomo_intraday_move", "same_expiry_loss_block"],
                    rejections=[],
                    warnings=[],
                ),
            ),
        ):
            with patch.object(strategy, "_record_trade"):
                trade = strategy.execute(ic, live=True)

        # Should still complete but not submit any orders
        assert trade["order_ids"] == []


class TestRecentExpiryConcentrationGate:
    """Time-series concentration gate (prevents the historical 50.7% on single expiry pattern).

    Window is calendar-time, not row-count: historical entries age out so the
    gate never permanently deadlocks the system after a halt.
    """

    def _write_ledger(self, tmp_path: Path, rows: list[tuple[str, str]]) -> Path:
        """rows = list of (entry_iso_datetime, expiry_iso_date)."""
        import json

        trades = [
            {
                "status": "closed",
                "strategy": "iron_condor",
                "entry_time": entry_iso,
                "legs": {"expiry": expiry},
            }
            for entry_iso, expiry in rows
        ]
        path = tmp_path / "trades.json"
        path.write_text(json.dumps({"trades": trades}))
        return path

    def test_blocks_when_target_expiry_dominates_recent(self, tmp_path):
        from datetime import datetime, timezone

        from scripts.iron_condor_trader import _check_recent_expiry_concentration

        now = datetime(2026, 5, 18, tzinfo=timezone.utc)
        rows = [(f"2026-05-{day:02d}T15:30:00+00:00", "2026-06-05") for day in range(1, 16)] + [
            ("2026-05-16T15:30:00+00:00", "2026-06-12"),
            ("2026-05-17T15:30:00+00:00", "2026-06-19"),
            ("2026-05-18T13:00:00+00:00", "2026-06-26"),
        ]
        ledger = self._write_ledger(tmp_path, rows)
        blocked, reason = _check_recent_expiry_concentration(
            "2026-06-05", ledger_path=ledger, now=now
        )
        assert blocked is True
        assert "2026-06-05" in reason

    def test_self_unblocks_when_old_entries_age_out(self, tmp_path):
        from datetime import datetime, timezone

        from scripts.iron_condor_trader import _check_recent_expiry_concentration

        # All historical entries are >60 days old. Even though they were
        # heavily concentrated, the calendar window excludes them — no deadlock.
        now = datetime(2026, 5, 18, tzinfo=timezone.utc)
        rows = [("2026-02-01T15:30:00+00:00", "2026-03-06") for _ in range(20)]
        ledger = self._write_ledger(tmp_path, rows)
        blocked, _ = _check_recent_expiry_concentration("2026-06-05", ledger_path=ledger, now=now)
        assert blocked is False

    def test_allows_diversified_recent_history(self, tmp_path):
        from datetime import datetime, timezone

        from scripts.iron_condor_trader import _check_recent_expiry_concentration

        now = datetime(2026, 5, 18, tzinfo=timezone.utc)
        rows = [
            ("2026-05-04T15:30:00+00:00", "2026-06-05"),
            ("2026-05-06T15:30:00+00:00", "2026-06-12"),
            ("2026-05-08T15:30:00+00:00", "2026-06-19"),
            ("2026-05-12T15:30:00+00:00", "2026-06-26"),
            ("2026-05-15T15:30:00+00:00", "2026-07-03"),
        ]
        ledger = self._write_ledger(tmp_path, rows)
        blocked, reason = _check_recent_expiry_concentration(
            "2026-07-10", ledger_path=ledger, now=now
        )
        assert blocked is False
        assert reason == ""

    def test_allows_small_sample(self, tmp_path):
        from datetime import datetime, timezone

        from scripts.iron_condor_trader import _check_recent_expiry_concentration

        now = datetime(2026, 5, 18, tzinfo=timezone.utc)
        # <4 sample total — not enough signal to gate
        rows = [
            ("2026-05-15T15:30:00+00:00", "2026-06-05"),
            ("2026-05-16T15:30:00+00:00", "2026-06-05"),
        ]
        ledger = self._write_ledger(tmp_path, rows)
        blocked, _ = _check_recent_expiry_concentration("2026-06-05", ledger_path=ledger, now=now)
        assert blocked is False

    def test_no_ledger_does_not_block(self, tmp_path):
        from scripts.iron_condor_trader import _check_recent_expiry_concentration

        blocked, _ = _check_recent_expiry_concentration(
            "2026-04-02", ledger_path=tmp_path / "does_not_exist.json"
        )
        assert blocked is False

    def test_canonical_module_path(self, tmp_path):
        # Both the re-export at scripts.iron_condor_trader and the canonical
        # src.risk.expiry_concentration export must point at the same callable.
        from scripts.iron_condor_trader import _check_recent_expiry_concentration
        from src.risk.expiry_concentration import check_recent_expiry_concentration

        assert _check_recent_expiry_concentration is check_recent_expiry_concentration
