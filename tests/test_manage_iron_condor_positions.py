"""Tests for iron condor position management.

Coverage:
- Exit at 50% profit
- Exit at 7 DTE
- Stop-loss at 100% of credit (positive EV config)
- Hold when no exit conditions met
- Config alignment with CLAUDE.md
- Zero credit edge case
- Group iron condors by expiry
- Close iron condor via MLeg order (mocked)
- Partial close scenarios (some legs fail)
- Option symbol parsing and DTE calculation

All Alpaca API calls are mocked. No real API calls.
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch


sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.manage_iron_condor_positions import (
    IC_EXIT_CONFIG,
    calculate_dte,
    check_exit_conditions,
    close_iron_condor,
    group_iron_condors,
    is_option_symbol,
    parse_option_symbol,
    record_trade_outcome,
)


class TestIsOptionSymbol:
    """Test option symbol detection."""

    def test_spy_stock_is_not_option(self):
        assert is_option_symbol("SPY") is False

    def test_short_symbol_is_not_option(self):
        assert is_option_symbol("AAPL") is False

    def test_occ_option_symbol_is_option(self):
        # SPY put expiring Feb 27, 2026 at $650 strike
        assert is_option_symbol("SPY260227P00650000") is True

    def test_occ_call_symbol_is_option(self):
        assert is_option_symbol("SPY260227C00620000") is True


class TestParseOptionSymbol:
    """Test OCC option symbol parsing."""

    def test_parse_spy_put(self):
        result = parse_option_symbol("SPY260227P00650000")
        assert result is not None
        assert result["underlying"] == "SPY"
        assert result["type"] == "P"
        assert result["strike"] == 650.0
        assert result["expiry"].year == 2026
        assert result["expiry"].month == 2
        assert result["expiry"].day == 27

    def test_parse_spy_call(self):
        result = parse_option_symbol("SPY260227C00620000")
        assert result is not None
        assert result["underlying"] == "SPY"
        assert result["type"] == "C"
        assert result["strike"] == 620.0

    def test_parse_stock_returns_none(self):
        result = parse_option_symbol("SPY")
        assert result is None


class TestCalculateDte:
    """Test DTE calculation."""

    def test_expiry_in_7_days(self):
        expiry = datetime.now() + timedelta(days=7)
        dte = calculate_dte(expiry)
        # Allow for partial day rounding
        assert 6 <= dte <= 7

    def test_expiry_in_30_days(self):
        expiry = datetime.now() + timedelta(days=30)
        dte = calculate_dte(expiry)
        # Allow for partial day rounding
        assert 29 <= dte <= 30

    def test_expired_option(self):
        expiry = datetime.now() - timedelta(days=1)
        dte = calculate_dte(expiry)
        assert dte < 0


class TestExitConditions:
    """Test iron condor exit condition logic."""

    def test_exit_at_7_dte(self):
        """Should exit when DTE <= 7."""
        ic = {
            "expiry": datetime.now() + timedelta(days=5),
            "total_pl": 50,
            "credit_received": 200,
        }
        should_exit, reason, _ = check_exit_conditions(ic)
        assert should_exit is True
        assert reason == "DTE_EXIT"

    def test_exit_at_50_percent_profit(self):
        """Should exit when profit >= 50% of credit."""
        ic = {
            "expiry": datetime.now() + timedelta(days=30),  # Not near expiry
            "total_pl": 110,  # 55% profit (above 50% target)
            "credit_received": 200,
        }
        should_exit, reason, _ = check_exit_conditions(ic)
        assert should_exit is True
        assert reason == "PROFIT_TARGET"

    def test_exit_at_100_percent_loss(self):
        """Should exit when loss >= 100% of credit per canonical config."""
        ic = {
            "expiry": datetime.now() + timedelta(days=30),
            "total_pl": -220,  # 110% loss (above 100% stop)
            "credit_received": 200,
        }
        should_exit, reason, _ = check_exit_conditions(ic)
        assert should_exit is True
        assert reason == "STOP_LOSS"

    def test_hold_when_no_exit_conditions_met(self):
        """Should hold when no exit conditions met."""
        ic = {
            "expiry": datetime.now() + timedelta(days=25),  # 25 DTE
            "total_pl": 40,  # 20% profit - not at target
            "credit_received": 200,
        }
        should_exit, reason, _ = check_exit_conditions(ic)
        assert should_exit is False
        assert reason == "HOLD"

    def test_config_values_aligned_with_strategy(self):
        """Verify config matches CLAUDE.md strategy."""
        assert IC_EXIT_CONFIG["profit_target_pct"] == 0.50  # 50% profit per LL-268
        assert IC_EXIT_CONFIG["stop_loss_pct"] == 1.00  # 100% stop per canonical constant
        assert IC_EXIT_CONFIG["exit_dte"] == 7  # 7 DTE per LL-268

    def test_zero_credit_returns_hold(self):
        """Zero credit received should not trigger any exit."""
        ic = {
            "expiry": datetime.now() + timedelta(days=30),
            "total_pl": 0,
            "credit_received": 0,
        }
        should_exit, reason, _ = check_exit_conditions(ic)
        assert should_exit is False


class TestGroupIronCondors:
    """Test grouping option legs into iron condors by expiry."""

    def test_group_four_legs_into_one_ic(self):
        """Four legs with same expiry should group into one iron condor."""
        expiry = datetime(2026, 3, 20)
        positions = [
            {
                "expiry": expiry,
                "underlying": "SPY",
                "qty": 1.0,
                "current_price": 0.50,
                "avg_entry_price": 1.00,
                "unrealized_pl": 50.0,
                "market_value": 50.0,
                "symbol": "SPY260320P00645000",
                "type": "P",
                "strike": 645.0,
            },
            {
                "expiry": expiry,
                "underlying": "SPY",
                "qty": -1.0,
                "current_price": 1.00,
                "avg_entry_price": 2.00,
                "unrealized_pl": 100.0,
                "market_value": -100.0,
                "symbol": "SPY260320P00655000",
                "type": "P",
                "strike": 655.0,
            },
            {
                "expiry": expiry,
                "underlying": "SPY",
                "qty": -1.0,
                "current_price": 0.80,
                "avg_entry_price": 1.50,
                "unrealized_pl": 70.0,
                "market_value": -80.0,
                "symbol": "SPY260320C00725000",
                "type": "C",
                "strike": 725.0,
            },
            {
                "expiry": expiry,
                "underlying": "SPY",
                "qty": 1.0,
                "current_price": 0.20,
                "avg_entry_price": 0.50,
                "unrealized_pl": -30.0,
                "market_value": 20.0,
                "symbol": "SPY260320C00735000",
                "type": "C",
                "strike": 735.0,
            },
        ]
        ics = group_iron_condors(positions)
        assert len(ics) == 1
        assert ics[0]["underlying"] == "SPY"
        assert len(ics[0]["legs"]) == 4
        assert ics[0]["expiry_str"] == "2026-03-20"

    def test_group_two_different_expiries(self):
        """Legs with different expiries should form separate iron condors."""
        positions = [
            {
                "expiry": datetime(2026, 3, 20),
                "underlying": "SPY",
                "qty": -1.0,
                "current_price": 1.0,
                "avg_entry_price": 2.0,
                "unrealized_pl": 100.0,
                "market_value": -100.0,
                "symbol": "SPY260320P00655000",
                "type": "P",
                "strike": 655.0,
            },
            {
                "expiry": datetime(2026, 4, 17),
                "underlying": "SPY",
                "qty": -1.0,
                "current_price": 1.5,
                "avg_entry_price": 2.5,
                "unrealized_pl": 100.0,
                "market_value": -150.0,
                "symbol": "SPY260417P00650000",
                "type": "P",
                "strike": 650.0,
            },
        ]
        ics = group_iron_condors(positions)
        assert len(ics) == 2


class TestCloseIronCondor:
    """Test closing iron condor positions via MLeg order."""

    def _make_ic(self):
        """Create a test iron condor dict."""
        return {
            "expiry": datetime(2026, 3, 20),
            "expiry_str": "2026-03-20",
            "underlying": "SPY",
            "legs": [
                {"symbol": "SPY260320P00645000", "qty": 1.0, "type": "P"},
                {"symbol": "SPY260320P00655000", "qty": -1.0, "type": "P"},
                {"symbol": "SPY260320C00725000", "qty": -1.0, "type": "C"},
                {"symbol": "SPY260320C00735000", "qty": 1.0, "type": "C"},
            ],
            "total_pl": 100.0,
            "credit_received": 200.0,
        }

    def test_dry_run_does_not_submit_order(self):
        """Dry run should succeed without submitting orders."""
        mock_client = MagicMock()
        ic = self._make_ic()

        result = close_iron_condor(mock_client, ic, "PROFIT_TARGET", dry_run=True)
        assert result is True
        mock_client.submit_order.assert_not_called()

    @patch("scripts.manage_iron_condor_positions.safe_submit_order")
    @patch("alpaca.trading.requests.MarketOrderRequest")
    def test_close_succeeds_with_mleg_order(self, mock_order_req, mock_submit):
        """Successful MLeg close should return True."""
        mock_order = MagicMock()
        mock_order.id = "order-123"
        mock_order.status = "accepted"
        mock_submit.return_value = mock_order
        mock_order_req.return_value = MagicMock()

        mock_client = MagicMock()
        ic = self._make_ic()

        result = close_iron_condor(mock_client, ic, "DTE_EXIT", dry_run=False)
        assert result is True
        mock_submit.assert_called_once()

    @patch("scripts.manage_iron_condor_positions.safe_submit_order")
    @patch("alpaca.trading.requests.MarketOrderRequest")
    def test_close_fails_preserves_all_legs(self, mock_order_req, mock_submit):
        """MLeg close failure should return False (all legs preserved)."""
        mock_order_req.return_value = MagicMock()
        mock_submit.side_effect = Exception("Order rejected by exchange")

        mock_client = MagicMock()
        ic = self._make_ic()

        result = close_iron_condor(mock_client, ic, "STOP_LOSS", dry_run=False)
        assert result is False


class TestRecordTradeOutcome:
    """Test trade outcome recording to Thompson model and trajectory log."""

    def _make_ic(self, pl=100.0, credit=200.0):
        return {
            "expiry_str": "2026-03-20",
            "underlying": "SPY",
            "total_pl": pl,
            "credit_received": credit,
            "legs": [],
        }

    def test_win_updates_thompson_model(self, tmp_path):
        """Integration test: win updates Thompson model file."""
        model = {
            "model_type": "thompson_sampling",
            "iron_condor": {"alpha": 2.0, "beta": 1.0, "wins": 1, "losses": 0},
            "spy_specific": {"alpha": 2.0, "beta": 1.0, "wins": 1, "losses": 0},
            "last_updated": "2026-01-26T00:00:00",
        }
        model_path = tmp_path / "models" / "ml" / "trade_confidence_model.json"
        model_path.parent.mkdir(parents=True)
        with open(model_path, "w") as f:
            json.dump(model, f)

        ic = self._make_ic(pl=100.0, credit=200.0)

        with patch("scripts.manage_iron_condor_positions.Path") as MockPath:

            def path_factory(*args):
                p = Path(*args)
                return p

            MockPath.side_effect = path_factory
            MockPath.__truediv__ = Path.__truediv__

            # Patch __file__ resolution in the module
            import scripts.manage_iron_condor_positions as mod

            with patch.object(mod, "__file__", str(tmp_path / "scripts" / "manage.py")):
                # Create scripts dir so parent.parent works
                (tmp_path / "scripts").mkdir(exist_ok=True)
                record_trade_outcome(ic, "PROFIT_TARGET", won=True)

        with open(model_path) as f:
            updated = json.load(f)

        assert updated["iron_condor"]["alpha"] == 3.0
        assert updated["iron_condor"]["wins"] == 2
        assert updated["iron_condor"]["beta"] == 1.0
        assert updated["iron_condor"]["losses"] == 0

    def test_loss_updates_thompson_model(self, tmp_path):
        """Integration test: loss updates Thompson model file."""
        model = {
            "model_type": "thompson_sampling",
            "iron_condor": {"alpha": 2.0, "beta": 1.0, "wins": 1, "losses": 0},
            "spy_specific": {"alpha": 2.0, "beta": 1.0, "wins": 1, "losses": 0},
            "last_updated": "2026-01-26T00:00:00",
        }
        model_path = tmp_path / "models" / "ml" / "trade_confidence_model.json"
        model_path.parent.mkdir(parents=True)
        with open(model_path, "w") as f:
            json.dump(model, f)

        ic = self._make_ic(pl=-250.0, credit=200.0)

        import scripts.manage_iron_condor_positions as mod

        with patch.object(mod, "__file__", str(tmp_path / "scripts" / "manage.py")):
            (tmp_path / "scripts").mkdir(exist_ok=True)
            record_trade_outcome(ic, "STOP_LOSS", won=False)

        with open(model_path) as f:
            updated = json.load(f)

        assert updated["iron_condor"]["alpha"] == 2.0
        assert updated["iron_condor"]["wins"] == 1
        assert updated["iron_condor"]["beta"] == 2.0
        assert updated["iron_condor"]["losses"] == 1

    def test_trajectory_log_written(self, tmp_path):
        """Trade outcome should append to trajectory JSONL."""
        model = {
            "model_type": "thompson_sampling",
            "iron_condor": {"alpha": 1.0, "beta": 1.0, "wins": 0, "losses": 0},
            "spy_specific": {"alpha": 1.0, "beta": 1.0, "wins": 0, "losses": 0},
            "last_updated": "2026-01-26T00:00:00",
        }
        model_path = tmp_path / "models" / "ml" / "trade_confidence_model.json"
        model_path.parent.mkdir(parents=True)
        with open(model_path, "w") as f:
            json.dump(model, f)

        ic = self._make_ic(pl=80.0, credit=200.0)

        import scripts.manage_iron_condor_positions as mod

        with patch.object(mod, "__file__", str(tmp_path / "scripts" / "manage.py")):
            (tmp_path / "scripts").mkdir(exist_ok=True)
            record_trade_outcome(ic, "DTE_EXIT", won=False)

        traj_path = tmp_path / "data" / "feedback" / "trade_trajectories.jsonl"
        assert traj_path.exists()
        with open(traj_path) as f:
            entry = json.loads(f.readline())
        assert entry["strategy"] == "iron_condor"
        assert entry["exit_reason"] == "DTE_EXIT"
        assert entry["won"] is False
        assert entry["pnl"] == 80.0
