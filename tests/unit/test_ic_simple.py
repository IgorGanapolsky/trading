"""Tests for ic_simple.py — the primary iron condor trading pipeline.

Covers: StrikeSelection.net_credit, find_opportunity, _wait_for_fill,
price-walking, and full E2E pipeline with mocked Alpaca client.
"""

import json
import logging
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import sys as _sys

# Stub out heavy dependencies not installed locally (alpaca, numpy, etc.)
import types

from src.markets.option_chain import StrikeSelection


def _ensure_module(name):
    """Create stub module if not already importable.

    FIX Apr 3, 2026: Only stub modules that don't exist as real packages.
    Previously, this would overwrite src.safety (a real package) with a bare
    ModuleType, causing 'src.safety is not a package' errors in later tests.
    """
    if name not in _sys.modules:
        parts = name.split(".")
        for i in range(len(parts)):
            partial = ".".join(parts[: i + 1])
            if partial not in _sys.modules:
                # Don't stub src.* packages that exist on disk.
                try:
                    __import__(partial)
                except ImportError:
                    module = types.ModuleType(partial)
                    _sys.modules[partial] = module
                    if i > 0:
                        parent_name = ".".join(parts[:i])
                        parent = _sys.modules[parent_name]
                        setattr(parent, parts[i], module)


# Alpaca SDK stubs
for mod in [
    "alpaca",
    "alpaca.trading",
    "alpaca.trading.client",
    "alpaca.trading.enums",
    "alpaca.trading.requests",
    "alpaca.data",
    "alpaca.data.historical",
    "alpaca.data.historical.option",
    "alpaca.data.requests",
    "alpaca.data.timeframe",
]:
    _ensure_module(mod)

# Create mock enums/classes that place_ic imports
_client = cast(Any, _sys.modules["alpaca.trading.client"])
_client.TradingClient = type(
    "TradingClient",
    (),
    {
        "__init__": lambda self, *args, **kwargs: None,
    },
)

_enums = _sys.modules["alpaca.trading.enums"]
# FIX Apr 3, 2026: Use enum-like objects with .value/.name so downstream code
# (guardian, scorecard) that accesses .value doesn't crash with AttributeError.


class _OrderClass(Enum):
    MLEG = "MLEG"
    SIMPLE = "SIMPLE"


class _OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class _TimeInForce(Enum):
    DAY = "day"
    GTC = "gtc"


class _QueryOrderStatus(Enum):
    CLOSED = "closed"
    OPEN = "open"
    ALL = "all"


_enums.OrderClass = _OrderClass
_enums.OrderSide = _OrderSide
_enums.TimeInForce = _TimeInForce
_enums.QueryOrderStatus = _QueryOrderStatus

_requests = _sys.modules["alpaca.trading.requests"]
_requests.LimitOrderRequest = type(
    "LimitOrderRequest",
    (),
    {
        "__init__": lambda self, **kw: self.__dict__.update(kw),
    },
)
_requests.MarketOrderRequest = type(
    "MarketOrderRequest",
    (),
    {
        "__init__": lambda self, **kw: self.__dict__.update(kw),
    },
)
_requests.OptionLegRequest = type(
    "OptionLegRequest",
    (),
    {
        "__init__": lambda self, **kw: self.__dict__.update(kw),
    },
)
_requests.GetOrdersRequest = type(
    "GetOrdersRequest",
    (),
    {
        "__init__": lambda self, **kw: self.__dict__.update(kw),
    },
)

# Safety gate stub
_ensure_module("src.safety.mandatory_trade_gate")
_safe_mod = _sys.modules["src.safety.mandatory_trade_gate"]
_safe_mod.safe_submit_order = lambda *a, **kw: None


# ══════════════════════════════════════════════════════════════════════════════
# 1. StrikeSelection.net_credit
# ══════════════════════════════════════════════════════════════════════════════


class TestStrikeSelectionNetCredit:
    """Verify net_credit = (short premiums) - (long premiums)."""

    def _make_selection(self, put_bid=0, call_bid=0, long_put_ask=0, long_call_ask=0):
        return StrikeSelection(
            short_put=620.0,
            long_put=610.0,
            short_call=680.0,
            long_call=690.0,
            put_delta=0.15,
            call_delta=0.15,
            method="live_delta",
            expiry="2026-05-01",
            put_bid=put_bid,
            call_bid=call_bid,
            long_put_ask=long_put_ask,
            long_call_ask=long_call_ask,
        )

    def test_net_credit_subtracts_long_legs(self):
        """The bug was: credit = put_bid + call_bid (ignoring long legs).
        Fixed: credit = (put_bid + call_bid) - (long_put_ask + long_call_ask).
        """
        sel = self._make_selection(
            put_bid=3.90,
            call_bid=3.89,  # Short legs: we collect $7.79 gross
            long_put_ask=2.50,
            long_call_ask=2.60,  # Long legs: we pay $5.10
        )
        # Net credit should be $7.79 - $5.10 = $2.69, NOT $7.79
        assert sel.net_credit == pytest.approx(2.69, abs=0.01)

    def test_net_credit_zero_long_legs(self):
        """If long legs have no ask data, net_credit equals gross."""
        sel = self._make_selection(put_bid=1.50, call_bid=1.00)
        assert sel.net_credit == pytest.approx(2.50)

    def test_net_credit_realistic_15_delta(self):
        """Realistic 15-delta $10-wide IC should yield $1.50-$3.50 net credit."""
        sel = self._make_selection(
            put_bid=2.10,
            call_bid=1.80,
            long_put_ask=1.20,
            long_call_ask=0.90,
        )
        credit = sel.net_credit
        assert 1.50 <= credit <= 3.50, f"Net credit ${credit:.2f} outside realistic range"

    def test_net_credit_never_equals_gross_when_wings_have_cost(self):
        """Regression: net credit must always be less than gross when wings cost money."""
        sel = self._make_selection(
            put_bid=4.00,
            call_bid=3.50,
            long_put_ask=1.00,
            long_call_ask=0.80,
        )
        gross = sel.put_bid + sel.call_bid
        assert sel.net_credit < gross
        assert sel.net_credit == pytest.approx(5.70)

    def test_net_credit_negative_when_wings_too_expensive(self):
        """If long legs cost more than short legs collect, credit is negative."""
        sel = self._make_selection(
            put_bid=1.00,
            call_bid=0.80,
            long_put_ask=1.50,
            long_call_ask=1.20,
        )
        assert sel.net_credit < 0


# ══════════════════════════════════════════════════════════════════════════════
# 2. find_opportunity — uses net_credit, not raw bids
# ══════════════════════════════════════════════════════════════════════════════


class TestFindOpportunity:
    """Verify find_opportunity uses selection.net_credit."""

    def _mock_selection(self, net_credit_val, method="live_delta"):
        sel = StrikeSelection(
            short_put=620.0,
            long_put=610.0,
            short_call=680.0,
            long_call=690.0,
            put_delta=0.15,
            call_delta=0.15,
            method=method,
            expiry="2026-05-01",
            put_bid=3.90,
            call_bid=3.89,
            # Set long asks so net_credit matches desired value
            long_put_ask=(3.90 + 3.89 - net_credit_val) / 2,
            long_call_ask=(3.90 + 3.89 - net_credit_val) / 2,
        )
        return sel

    @patch("src.markets.option_chain.select_strikes_by_delta")
    def test_uses_net_credit_not_gross(self, mock_select):
        """The returned est_credit must be net_credit, not put_bid + call_bid."""
        from scripts.ic_simple import find_opportunity

        mock_select.return_value = self._mock_selection(net_credit_val=2.50)
        opp = find_opportunity(spy_price=650.0)

        assert opp is not None
        assert opp["est_credit"] == pytest.approx(2.50, abs=0.02)
        # Must NOT be the gross $7.79
        assert opp["est_credit"] < 5.0

    @patch("src.markets.option_chain.select_strikes_by_delta")
    def test_rejects_below_min_credit(self, mock_select):
        from scripts.ic_simple import find_opportunity

        mock_select.return_value = self._mock_selection(net_credit_val=0.30)
        opp = find_opportunity(spy_price=650.0)
        assert opp is None

    @patch("src.markets.option_chain.select_strikes_by_delta")
    def test_returns_delta_provenance_for_audit(self, mock_select):
        from scripts.ic_simple import TARGET_DELTA, find_opportunity

        mock_select.return_value = self._mock_selection(net_credit_val=2.10)
        opp = find_opportunity(spy_price=650.0)

        assert opp is not None
        assert opp["method"] == "live_delta"
        assert opp["put_delta"] == pytest.approx(0.15)
        assert opp["call_delta"] == pytest.approx(0.15)
        assert opp["target_delta"] == TARGET_DELTA

    @patch("src.markets.option_chain.select_strikes_by_delta")
    def test_heuristic_fallback_uses_conservative_estimate(self, mock_select):
        from scripts.ic_simple import find_opportunity

        mock_select.return_value = self._mock_selection(
            net_credit_val=0.0, method="heuristic_fallback"
        )
        opp = find_opportunity(spy_price=650.0)
        assert opp is not None
        assert opp["est_credit"] == pytest.approx(1.50)


# ══════════════════════════════════════════════════════════════════════════════
# 3. _wait_for_fill
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class MockOrder:
    id: str = "test-order-123"
    status: str = "PENDING_NEW"
    filled_avg_price: float | None = None


class TestWaitForFill:
    """Verify fill detection handles all terminal states."""

    @patch("time.sleep")
    def test_returns_true_on_filled(self, mock_sleep):
        from scripts.ic_simple import _wait_for_fill

        client = MagicMock()
        filled_order = MockOrder(status="OrderStatus.FILLED", filled_avg_price=2.45)
        client.get_order_by_id.return_value = filled_order

        result = _wait_for_fill(client, "test-123", timeout_seconds=30, poll_interval=5)
        assert result is True

    @patch("time.sleep")
    def test_returns_false_on_expired(self, mock_sleep):
        from scripts.ic_simple import _wait_for_fill

        client = MagicMock()
        client.get_order_by_id.return_value = MockOrder(status="OrderStatus.EXPIRED")

        result = _wait_for_fill(client, "test-123", timeout_seconds=30, poll_interval=5)
        assert result is False

    @patch("time.sleep")
    def test_returns_false_on_canceled(self, mock_sleep):
        from scripts.ic_simple import _wait_for_fill

        client = MagicMock()
        client.get_order_by_id.return_value = MockOrder(status="OrderStatus.CANCELED")

        result = _wait_for_fill(client, "test-123", timeout_seconds=30, poll_interval=5)
        assert result is False

    @patch("time.sleep")
    def test_returns_false_on_rejected(self, mock_sleep):
        from scripts.ic_simple import _wait_for_fill

        client = MagicMock()
        client.get_order_by_id.return_value = MockOrder(status="OrderStatus.REJECTED")

        result = _wait_for_fill(client, "test-123", timeout_seconds=30, poll_interval=5)
        assert result is False

    @patch("time.sleep")
    def test_returns_false_on_timeout(self, mock_sleep):
        from scripts.ic_simple import _wait_for_fill

        client = MagicMock()
        # Always returns pending — never fills
        client.get_order_by_id.return_value = MockOrder(status="OrderStatus.PENDING_NEW")

        result = _wait_for_fill(client, "test-123", timeout_seconds=10, poll_interval=5)
        assert result is False
        # Should have polled twice (0s, 5s) then timed out
        assert client.get_order_by_id.call_count == 2

    @patch("time.sleep")
    def test_fills_on_second_poll(self, mock_sleep):
        from scripts.ic_simple import _wait_for_fill

        client = MagicMock()
        # First poll: pending. Second poll: filled.
        client.get_order_by_id.side_effect = [
            MockOrder(status="OrderStatus.PENDING_NEW"),
            MockOrder(status="OrderStatus.FILLED", filled_avg_price=2.30),
        ]

        result = _wait_for_fill(client, "test-123", timeout_seconds=30, poll_interval=5)
        assert result is True
        assert client.get_order_by_id.call_count == 2


# ══════════════════════════════════════════════════════════════════════════════
# 4. Price-walk loop in place_ic
# ══════════════════════════════════════════════════════════════════════════════


class TestPriceWalk:
    """Verify price-walking: cancel, retry $0.05 worse, up to $0.20 max."""

    def _make_opp(self, est_credit=2.50):
        return {
            "expiry": "2026-05-01",
            "long_put": 610.0,
            "short_put": 620.0,
            "short_call": 680.0,
            "long_call": 690.0,
            "est_credit": est_credit,
            "method": "live_delta",
        }

    @patch("scripts.ic_simple._save_entries")
    @patch("scripts.ic_simple._load_entries", return_value={})
    @patch("scripts.ic_simple._wait_for_fill")
    @patch("src.safety.mandatory_trade_gate.safe_submit_order")
    def test_fills_on_first_attempt(self, mock_submit, mock_wait, mock_load, mock_save):
        from scripts.ic_simple import place_ic

        mock_order = MagicMock()
        mock_order.id = "order-1"
        mock_order.status = "FILLED"
        mock_submit.return_value = mock_order
        mock_wait.return_value = True  # Fills immediately

        result = place_ic(MagicMock(), self._make_opp(est_credit=2.50))

        # Should only submit once (no retry needed)
        assert mock_submit.call_count == 1
        assert result == "order-1"
        mock_save.assert_called_once()
        # Verify limit price: -(est_credit - 0.05) = -2.45
        submitted_request = mock_submit.call_args[0][1]
        assert submitted_request.limit_price == pytest.approx(-2.45)

    @patch("scripts.ic_simple._save_entries")
    @patch("scripts.ic_simple._load_entries", return_value={})
    @patch("scripts.ic_simple._wait_for_fill")
    @patch("src.safety.mandatory_trade_gate.safe_submit_order")
    def test_walks_price_on_no_fill(self, mock_submit, mock_wait, mock_load, mock_save):
        from scripts.ic_simple import place_ic

        mock_order = MagicMock()
        mock_order.id = "order-1"
        mock_order.status = "PENDING_NEW"
        mock_submit.return_value = mock_order

        # Fails first 3 times, fills on 4th ($0.15 concession)
        mock_wait.side_effect = [False, False, False, True]

        client = MagicMock()
        place_ic(client, self._make_opp(est_credit=2.50))

        # Should submit 4 times (initial + 3 retries)
        assert mock_submit.call_count == 4
        # Should cancel 3 times (each failed attempt)
        assert client.cancel_order_by_id.call_count == 3

        # Verify each limit price walks $0.05 worse
        prices = [call[0][1].limit_price for call in mock_submit.call_args_list]
        assert prices[0] == pytest.approx(-2.45)  # Initial: est - 0.05
        assert prices[1] == pytest.approx(-2.40)  # Walk 1: -0.05
        assert prices[2] == pytest.approx(-2.35)  # Walk 2: -0.10
        assert prices[3] == pytest.approx(-2.30)  # Walk 3: -0.15

    @patch("scripts.ic_simple._save_entries")
    @patch("scripts.ic_simple._load_entries", return_value={})
    @patch("scripts.ic_simple._wait_for_fill", return_value=False)
    @patch("src.safety.mandatory_trade_gate.safe_submit_order")
    def test_stops_at_max_walk(self, mock_submit, mock_wait, mock_load, mock_save):
        from scripts.ic_simple import place_ic

        mock_order = MagicMock()
        mock_order.id = "order-1"
        mock_order.status = "PENDING_NEW"
        mock_submit.return_value = mock_order

        client = MagicMock()
        result = place_ic(client, self._make_opp(est_credit=2.50))

        # MAX_WALK = 0.20, WALK_INCREMENT = 0.05 → 5 attempts (0, 0.05, 0.10, 0.15, 0.20)
        assert mock_submit.call_count == 5
        assert result is None
        mock_save.assert_not_called()

    @patch("scripts.ic_simple._save_entries")
    @patch("scripts.ic_simple._load_entries", return_value={})
    @patch("scripts.ic_simple._wait_for_fill", return_value=False)
    @patch("src.safety.mandatory_trade_gate.safe_submit_order")
    def test_stops_at_min_credit(self, mock_submit, mock_wait, mock_load, mock_save):
        from scripts.ic_simple import place_ic

        mock_order = MagicMock()
        mock_order.id = "order-1"
        mock_order.status = "PENDING_NEW"
        mock_submit.return_value = mock_order

        client = MagicMock()
        # est_credit = 0.60, limit = 0.55. After walk $0.05 → 0.50 (MIN). After $0.10 → 0.45 < MIN → stop
        result = place_ic(client, self._make_opp(est_credit=0.60))

        # Should submit only 2 times: at $0.55 and $0.50 (then $0.45 < MIN_CREDIT stops)
        assert mock_submit.call_count == 2
        assert result is None
        mock_save.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# 5. Thompson validation-reset gate
# ══════════════════════════════════════════════════════════════════════════════


class TestThompsonValidationResetGate:
    def test_low_thompson_blocks_without_validation_reset(self, tmp_path, monkeypatch):
        import scripts.ic_simple as ic

        state_file = tmp_path / "system_state.json"
        state_file.write_text(json.dumps({"north_star_weekly_gate": {"mode": "validation"}}))
        monkeypatch.setattr(ic, "SYSTEM_STATE_FILE", state_file)

        should_skip, reason = ic._should_skip_for_thompson(0.277)

        assert should_skip is True
        assert "skip entry" in reason

    def test_low_thompson_allows_controlled_paper_validation_reset(
        self, tmp_path, monkeypatch
    ):
        import scripts.ic_simple as ic

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
            )
        )
        monkeypatch.setattr(ic, "SYSTEM_STATE_FILE", state_file)

        should_skip, reason = ic._should_skip_for_thompson(0.277)

        assert should_skip is False
        assert "controlled paper validation" in reason
        assert "live/scaling remains blocked" in reason


# ══════════════════════════════════════════════════════════════════════════════
# 6. Reporting: validation slice must not mask lifetime ledger
# ══════════════════════════════════════════════════════════════════════════════


class TestNorthStarReadinessReport:
    def test_print_report_includes_lifetime_ledger_and_gate_state(
        self, tmp_path, monkeypatch, caplog
    ):
        import scripts.ic_simple as ic

        stats_file = tmp_path / "ic_stats.json"
        stats_file.write_text(
            json.dumps(
                {
                    "total": 1,
                    "wins": 1,
                    "losses": 0,
                    "win_rate": 100.0,
                    "profit_factor": 999.0,
                    "total_pnl": 41.0,
                    "avg_win": 41.0,
                    "avg_loss": 0.0,
                }
            )
        )
        trades_file = tmp_path / "trades.json"
        trades_file.write_text(
            json.dumps(
                {
                    "stats": {
                        "closed_trades": 66,
                        "wins": 16,
                        "losses": 49,
                        "win_rate_pct": 24.24,
                        "profit_factor": 0.25,
                        "total_realized_pnl": -3402.0,
                    }
                }
            )
        )
        state_file = tmp_path / "system_state.json"
        state_file.write_text(
            json.dumps(
                {
                    "north_star_weekly_gate": {
                        "mode": "validation_reset",
                        "scale_allowed": False,
                        "block_new_positions": True,
                        "blocker_reason": "lifetime ledger negative",
                    }
                }
            )
        )

        monkeypatch.setattr(ic, "IC_STATS_FILE", stats_file)
        monkeypatch.setattr(ic, "TRADE_LEDGER_FILE", trades_file)
        monkeypatch.setattr(ic, "SYSTEM_STATE_FILE", state_file)
        monkeypatch.setattr(ic, "JOURNAL_FILE", tmp_path / "missing.jsonl")

        caplog.set_level(logging.INFO, logger="ic_simple")
        ic._print_report()

        assert "NORTH STAR READINESS" in caplog.text
        assert "Validation slice: 1/30 closed trades" in caplog.text
        assert "Lifetime ledger: 66 closed" in caplog.text
        assert "win_rate=24.24%" in caplog.text
        assert "PF=0.25" in caplog.text
        assert "expectancy=$-51.55/trade" in caplog.text
        assert "mode=validation_reset" in caplog.text
        assert "scale_allowed=False" in caplog.text
        assert "block_new_positions=True" in caplog.text
        assert "lifetime ledger negative" in caplog.text


# ══════════════════════════════════════════════════════════════════════════════
# 7. E2E: Full pipeline mock
# ══════════════════════════════════════════════════════════════════════════════


class TestE2EPipeline:
    """End-to-end: mock Alpaca, run entry flow, verify correct credit in order."""

    @patch("scripts.ic_simple._save_entries")
    @patch("scripts.ic_simple._load_entries", return_value={})
    @patch("scripts.ic_simple._wait_for_fill", return_value=True)
    @patch("src.safety.mandatory_trade_gate.safe_submit_order")
    @patch("scripts.ic_simple.find_opportunity")
    @patch("scripts.ic_simple._get_thompson_confidence", return_value=0.90)
    @patch("scripts.ic_simple._count_open_ics", return_value=0)
    @patch("scripts.ic_simple._cancel_stale_orders")
    @patch("scripts.ic_simple._check_recent_fills")
    @patch("scripts.ic_simple.check_exits")
    @patch("scripts.ic_simple._refresh_canonical_state")
    @patch("scripts.ic_simple.get_spy_price", return_value=650.0)
    @patch("scripts.ic_simple.get_client")
    def test_full_entry_uses_net_credit_in_limit_price(
        self,
        mock_client_fn,
        mock_spy,
        mock_refresh,
        mock_exits,
        mock_fills,
        mock_stale,
        mock_count,
        mock_thompson,
        mock_opp,
        mock_submit,
        mock_wait,
        mock_load,
        mock_save,
    ):
        """The single most important test: verify the limit price sent to Alpaca
        is based on NET credit (~$2-3), not GROSS short bids (~$7-8)."""
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client

        # Simulate realistic opportunity with net credit $2.50
        mock_opp.return_value = {
            "expiry": "2026-05-01",
            "long_put": 610.0,
            "short_put": 620.0,
            "short_call": 680.0,
            "long_call": 690.0,
            "est_credit": 2.50,  # This is the NET credit
            "method": "live_delta",
        }

        mock_order = MagicMock()
        mock_order.id = "e2e-order-1"
        mock_order.status = "FILLED"
        mock_submit.return_value = mock_order

        # Run main with entry mode
        import scripts.ic_simple as ic

        class _Snapshot:
            label = "calm"
            regime_id = 0
            confidence = 0.85
            vix_level = 18.0
            transition_prediction = None

        # Patch sync freshness and re-entry gates (added Apr 2026)
        import json
        from datetime import datetime, timezone

        fresh_sync = {"sync_health": {"last_successful_sync": datetime.now(timezone.utc).isoformat()}}
        original_read = Path.read_text

        def _patched_read(self):
            if "system_state" in str(self):
                return json.dumps(fresh_sync)
            if "trades.json" in str(self):
                return json.dumps({"trades": []})
            return original_read(self)

        sys.argv = ["ic_simple.py", "--mode", "both"]
        with patch(
            "src.utils.regime_detector.RegimeDetector.detect_live_regime_with_prediction",
            return_value=_Snapshot(),
        ), patch.object(Path, "read_text", _patched_read):
            ic.main()

        # Verify order was submitted
        assert mock_submit.called

        # THE CRITICAL CHECK: limit price must be based on net credit
        submitted_request = mock_submit.call_args[0][1]
        limit_price = submitted_request.limit_price

        # limit_price should be negative (credit), around -2.45 (est - $0.05 concession)
        assert limit_price < 0, "Limit price must be negative for credit orders"
        assert abs(limit_price) < 5.0, (
            f"Limit ${abs(limit_price):.2f} too high — using gross bids, not net credit"
        )
        assert abs(limit_price) == pytest.approx(2.45, abs=0.25), (
            f"Expected ~$2.45 limit (net $2.50 - $0.05), got ${abs(limit_price):.2f}"
        )

    @patch("scripts.ic_simple._save_entries")
    @patch("scripts.ic_simple._load_entries", return_value={})
    @patch("scripts.ic_simple._wait_for_fill", return_value=True)
    @patch("src.safety.mandatory_trade_gate.safe_submit_order")
    @patch("scripts.ic_simple.find_opportunity")
    @patch("scripts.ic_simple._count_open_ics", return_value=0)
    @patch("scripts.ic_simple._cancel_stale_orders")
    @patch("scripts.ic_simple._check_recent_fills")
    @patch("scripts.ic_simple.check_exits")
    @patch("scripts.ic_simple._refresh_canonical_state")
    @patch("scripts.ic_simple.get_spy_price", return_value=650.0)
    @patch("scripts.ic_simple.get_client")
    def test_no_trade_when_position_limit_reached(
        self,
        mock_client_fn,
        mock_spy,
        mock_refresh,
        mock_exits,
        mock_fills,
        mock_stale,
        mock_count,
        mock_opp,
        mock_submit,
        mock_wait,
        mock_load,
        mock_save,
    ):
        mock_client_fn.return_value = MagicMock()
        mock_count.return_value = 4  # At MAX_IC limit

        import scripts.ic_simple as ic

        sys.argv = ["ic_simple.py", "--mode", "entry"]
        ic.main()

        # Should NOT submit any orders
        assert not mock_submit.called
