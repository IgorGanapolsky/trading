"""Tests for src/ml/grpo_trade_learner.py."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from src.ml.grpo_trade_learner import (
    GRPOTradeLearner,
    TradeFeatures,
    TradeParams,
    TradeRecord,
    get_optimal_trade_params,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_features(**overrides) -> TradeFeatures:
    defaults = dict(
        vix_level=18.0,
        vix_percentile=0.5,
        vix_term_structure=0.9,
        spy_20d_return=0.01,
        spy_5d_return=0.005,
        hour_of_day=0.5,
        day_of_week=0.4,
        days_to_expiry=30.0,
        put_call_ratio=1.0,
    )
    defaults.update(overrides)
    return TradeFeatures(**defaults)


def _make_params(**overrides) -> TradeParams:
    defaults = dict(
        delta=0.15,
        dte=30,
        entry_hour=0.5,
        exit_profit_pct=0.50,
        confidence=0.5,
    )
    defaults.update(overrides)
    return TradeParams(**defaults)


def _make_record(pnl: float = 100.0, outcome: str = "win", **kw) -> TradeRecord:
    return TradeRecord(
        features=kw.get("features", _make_features()),
        params=kw.get("params", _make_params()),
        pnl=pnl,
        pnl_pct=pnl / 750.0,  # rough approximation
        outcome=outcome,
        timestamp=kw.get("timestamp", datetime(2026, 2, 15)),
    )


# ---------------------------------------------------------------------------
# TradeFeatures
# ---------------------------------------------------------------------------


class TestTradeFeatures:
    def test_to_array_shape_and_dtype(self):
        f = _make_features()
        arr = f.to_array()
        assert arr.shape == (9,)
        assert arr.dtype == np.float32

    def test_to_array_normalization(self):
        f = _make_features(vix_level=25.0, days_to_expiry=60.0)
        arr = f.to_array()
        assert arr[0] == pytest.approx(25.0 / 50.0)  # vix normalized
        assert arr[7] == pytest.approx(60.0 / 60.0)  # dte normalized

    def test_to_array_returns_scaling(self):
        f = _make_features(spy_20d_return=0.02, spy_5d_return=-0.01)
        arr = f.to_array()
        assert arr[3] == pytest.approx(0.02 * 10)
        assert arr[4] == pytest.approx(-0.01 * 10)


# ---------------------------------------------------------------------------
# TradeParams
# ---------------------------------------------------------------------------


class TestTradeParams:
    def test_to_dict_keys(self):
        p = _make_params()
        d = p.to_dict()
        assert set(d.keys()) == {"delta", "dte", "entry_hour", "exit_profit_pct", "confidence"}

    def test_to_dict_rounding(self):
        p = _make_params(delta=0.15678, entry_hour=0.12345, confidence=0.98765)
        d = p.to_dict()
        assert d["delta"] == 0.157  # 3 decimals
        assert d["entry_hour"] == 0.12  # 2 decimals
        assert d["confidence"] == 0.988  # 3 decimals


# ---------------------------------------------------------------------------
# TradeRecord
# ---------------------------------------------------------------------------


class TestTradeRecord:
    def test_to_dict_has_required_fields(self):
        rec = _make_record(pnl=150.0, outcome="win")
        d = rec.to_dict()
        assert d["pnl"] == 150.0
        assert d["outcome"] == "win"
        assert "features" in d
        assert "params" in d
        assert "timestamp" in d

    def test_to_dict_timestamp_iso(self):
        ts = datetime(2026, 3, 1, 14, 30)
        rec = _make_record(timestamp=ts)
        d = rec.to_dict()
        assert d["timestamp"] == ts.isoformat()


# ---------------------------------------------------------------------------
# GRPOTradeLearner — construction
# ---------------------------------------------------------------------------


class TestGRPOTradeLearnerInit:
    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_init_without_torch(self):
        learner = GRPOTradeLearner()
        assert learner.policy is None
        assert learner.optimizer is None

    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_fallback_params_set(self):
        learner = GRPOTradeLearner()
        fp = learner._fallback_params
        assert fp.delta == 0.15
        assert fp.dte == 30
        assert fp.exit_profit_pct == 0.50

    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_custom_hyperparams(self):
        learner = GRPOTradeLearner(learning_rate=0.01, batch_size=32, gamma=0.95, group_size=4)
        assert learner.learning_rate == 0.01
        assert learner.batch_size == 32
        assert learner.gamma == 0.95
        assert learner.group_size == 4


# ---------------------------------------------------------------------------
# calculate_rewards
# ---------------------------------------------------------------------------


class TestCalculateRewards:
    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_empty_history(self):
        learner = GRPOTradeLearner()
        rewards = learner.calculate_rewards()
        assert len(rewards) == 0

    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_single_trade(self):
        learner = GRPOTradeLearner()
        learner.trade_history = [_make_record(pnl=200.0)]
        rewards = learner.calculate_rewards()
        assert len(rewards) == 1
        assert rewards[0] == pytest.approx(200.0)

    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_group_relative_normalization(self):
        learner = GRPOTradeLearner()
        learner.trade_history = [
            _make_record(pnl=100.0),
            _make_record(pnl=200.0),
            _make_record(pnl=300.0),
        ]
        rewards = learner.calculate_rewards()
        # Mean-centered and std-normalized
        assert rewards.mean() == pytest.approx(0.0, abs=1e-6)
        assert rewards.std() == pytest.approx(1.0, abs=0.15)

    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_rewards_clipped_to_bounds(self):
        learner = GRPOTradeLearner()
        # Create trades with extreme outlier
        trades = [_make_record(pnl=100.0) for _ in range(20)]
        trades.append(_make_record(pnl=100_000.0))  # extreme outlier
        learner.trade_history = trades
        rewards = learner.calculate_rewards()
        assert rewards.max() <= 3.0
        assert rewards.min() >= -3.0

    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_zero_std_no_division_error(self):
        """All identical P/L => std=0, should not raise."""
        learner = GRPOTradeLearner()
        learner.trade_history = [_make_record(pnl=100.0) for _ in range(5)]
        rewards = learner.calculate_rewards()
        assert len(rewards) == 5
        # All the same => advantage = 0 for all
        assert all(r == pytest.approx(0.0) for r in rewards)


# ---------------------------------------------------------------------------
# load_trade_history
# ---------------------------------------------------------------------------


class TestLoadTradeHistory:
    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_missing_file_returns_zero(self, tmp_path):
        learner = GRPOTradeLearner()
        result = learner.load_trade_history(tmp_path / "does_not_exist.json")
        assert result == 0
        assert learner.trade_history == []

    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_malformed_json_returns_zero(self, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{not valid json!!!")
        learner = GRPOTradeLearner()
        result = learner.load_trade_history(bad_file)
        assert result == 0

    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_empty_trade_history(self, tmp_path):
        f = tmp_path / "state.json"
        f.write_text(json.dumps({"trade_history": []}))
        learner = GRPOTradeLearner()
        result = learner.load_trade_history(f)
        assert result == 0

    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_loads_option_trades(self, tmp_path):
        trades = [
            {
                "symbol": "SPY260227P00655000",
                "filled_at": "2026-02-20T10:30:00Z",
                "price": "1.50",
                "qty": "1",
                "side": "SELL",
            },
            {
                "symbol": "SPY260227P00645000",
                "filled_at": "2026-02-20T10:30:00Z",
                "price": "0.80",
                "qty": "1",
                "side": "BUY",
            },
        ]
        f = tmp_path / "state.json"
        f.write_text(json.dumps({"trade_history": trades}))
        learner = GRPOTradeLearner()
        result = learner.load_trade_history(f)
        assert result >= 1

    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_skips_null_symbol(self, tmp_path):
        trades = [
            {
                "symbol": None,
                "filled_at": "2026-02-20T10:30:00Z",
                "price": "1.0",
                "qty": "1",
                "side": "SELL",
            },
        ]
        f = tmp_path / "state.json"
        f.write_text(json.dumps({"trade_history": trades}))
        learner = GRPOTradeLearner()
        result = learner.load_trade_history(f)
        assert result == 0

    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_skips_trades_without_filled_at(self, tmp_path):
        trades = [
            {"symbol": "SPY260227P00655000", "price": "1.0", "qty": "1", "side": "SELL"},
        ]
        f = tmp_path / "state.json"
        f.write_text(json.dumps({"trade_history": trades}))
        learner = GRPOTradeLearner()
        result = learner.load_trade_history(f)
        assert result == 0


# ---------------------------------------------------------------------------
# _process_raw_trades
# ---------------------------------------------------------------------------


class TestProcessRawTrades:
    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_sell_credit_buy_debit(self):
        """SELL adds credit, BUY subtracts debit."""
        trades = [
            {
                "symbol": "SPY260227P00655000",
                "filled_at": "2026-02-20T10:30:00Z",
                "price": "2.00",
                "qty": "1",
                "side": "SELL",
            },
            {
                "symbol": "SPY260227P00645000",
                "filled_at": "2026-02-20T10:31:00Z",
                "price": "1.00",
                "qty": "1",
                "side": "BUY",
            },
        ]
        learner = GRPOTradeLearner()
        records = learner._process_raw_trades(trades)
        assert len(records) == 1
        # net = (2.00 * 1 * 100) - (1.00 * 1 * 100) = 100
        assert records[0].pnl == pytest.approx(100.0)
        assert records[0].outcome == "win"

    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_loss_outcome(self):
        trades = [
            {
                "symbol": "SPY260227C00700000",
                "filled_at": "2026-02-20T11:00:00Z",
                "price": "0.50",
                "qty": "1",
                "side": "SELL",
            },
            {
                "symbol": "SPY260227C00710000",
                "filled_at": "2026-02-20T11:00:00Z",
                "price": "1.50",
                "qty": "1",
                "side": "BUY",
            },
        ]
        learner = GRPOTradeLearner()
        records = learner._process_raw_trades(trades)
        assert len(records) == 1
        # net = (0.50 * 100) - (1.50 * 100) = -100
        assert records[0].pnl == pytest.approx(-100.0)
        assert records[0].outcome == "loss"

    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_non_option_trades_ignored(self):
        trades = [
            {
                "symbol": "AAPL",
                "filled_at": "2026-02-20T10:00:00Z",
                "price": "180.00",
                "qty": "10",
                "side": "BUY",
            },
        ]
        learner = GRPOTradeLearner()
        records = learner._process_raw_trades(trades)
        assert len(records) == 0

    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_groups_trades_by_date(self):
        trades = [
            {
                "symbol": "SPY260227P00655000",
                "filled_at": "2026-02-20T10:30:00Z",
                "price": "1.50",
                "qty": "1",
                "side": "SELL",
            },
            {
                "symbol": "SPY260227P00655000",
                "filled_at": "2026-02-21T10:30:00Z",
                "price": "1.50",
                "qty": "1",
                "side": "SELL",
            },
        ]
        learner = GRPOTradeLearner()
        records = learner._process_raw_trades(trades)
        assert len(records) == 2  # two different dates


# ---------------------------------------------------------------------------
# predict_optimal_params
# ---------------------------------------------------------------------------


class TestPredictOptimalParams:
    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_fallback_without_torch(self):
        learner = GRPOTradeLearner()
        params = learner.predict_optimal_params(_make_features())
        assert params.delta == 0.15
        assert params.dte == 30
        assert params.confidence == 0.5

    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_predict_with_none_features_uses_defaults(self):
        learner = GRPOTradeLearner()
        params = learner.predict_optimal_params(None)
        # Should still return valid TradeParams (fallback)
        assert isinstance(params, TradeParams)
        assert 0.10 <= params.delta <= 0.25
        assert 21 <= params.dte <= 60


# ---------------------------------------------------------------------------
# train_policy
# ---------------------------------------------------------------------------


class TestTrainPolicy:
    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_train_without_torch(self):
        learner = GRPOTradeLearner()
        result = learner.train_policy(epochs=10)
        assert "error" in result
        assert "PyTorch" in result["error"]

    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_train_insufficient_trades(self):
        # Build learner with torch disabled so __init__ skips real torch setup
        with patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False):
            learner = GRPOTradeLearner(batch_size=16)
        learner.trade_history = [_make_record() for _ in range(5)]
        # Now enable the flag so train_policy passes the torch check and
        # reaches the trade-count guard instead
        with patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", True):
            result = learner.train_policy(epochs=10)
        assert "error" in result
        assert "Need at least 16 trades" in result["error"]


# ---------------------------------------------------------------------------
# get_learning_summary
# ---------------------------------------------------------------------------


class TestGetLearningSummary:
    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_no_history(self):
        learner = GRPOTradeLearner()
        summary = learner.get_learning_summary()
        assert summary == {"error": "No trade history loaded"}

    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_summary_with_trades(self):
        learner = GRPOTradeLearner()
        learner.trade_history = [
            _make_record(pnl=150.0, outcome="win"),
            _make_record(pnl=200.0, outcome="win"),
            _make_record(pnl=-100.0, outcome="loss"),
        ]
        summary = learner.get_learning_summary()
        assert summary["total_trades"] == 3
        assert summary["win_rate"] == pytest.approx(2.0 / 3.0)
        assert summary["avg_win_pnl"] == pytest.approx(175.0)
        assert summary["avg_loss_pnl"] == pytest.approx(-100.0)
        assert summary["torch_available"] is False

    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_summary_all_wins(self):
        learner = GRPOTradeLearner()
        learner.trade_history = [_make_record(pnl=100.0, outcome="win") for _ in range(3)]
        summary = learner.get_learning_summary()
        assert summary["win_rate"] == 1.0
        # profit_factor: no losses => total_loss_pnl=0 => profit_factor=0
        assert summary["profit_factor"] == 0

    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_summary_all_losses(self):
        learner = GRPOTradeLearner()
        learner.trade_history = [_make_record(pnl=-50.0, outcome="loss") for _ in range(3)]
        summary = learner.get_learning_summary()
        assert summary["win_rate"] == 0.0
        assert summary["avg_win_pnl"] == 0
        assert summary["winning_conditions"] == {}


# ---------------------------------------------------------------------------
# save_model / load_model
# ---------------------------------------------------------------------------


class TestModelPersistence:
    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_save_without_torch_writes_metadata(self, tmp_path):
        metadata_path = tmp_path / "metadata.json"
        with patch("src.ml.grpo_trade_learner.METADATA_PATH", metadata_path):
            learner = GRPOTradeLearner()
            learner.save_model()
            assert metadata_path.exists()
            meta = json.loads(metadata_path.read_text())
            assert meta["torch_available"] is False
            assert "fallback_params" in meta
            assert "config" in meta

    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    def test_load_model_no_file(self, tmp_path):
        with patch("src.ml.grpo_trade_learner.MODEL_PATH", tmp_path / "no_model.pt"):
            learner = GRPOTradeLearner()
            result = learner.load_model()
            assert result is False

    def test_load_model_without_torch(self, tmp_path):
        # Even if file exists, no torch => False
        fake = tmp_path / "fake_model.pt"
        fake.touch()
        with (
            patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False),
            patch("src.ml.grpo_trade_learner.MODEL_PATH", fake),
        ):
            learner = GRPOTradeLearner()
            result = learner.load_model()
            assert result is False


# ---------------------------------------------------------------------------
# get_optimal_trade_params (module-level helper)
# ---------------------------------------------------------------------------


class TestGetOptimalTradeParams:
    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_returns_trade_params(self):
        params = get_optimal_trade_params()
        assert isinstance(params, TradeParams)

    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_with_explicit_features(self):
        f = _make_features(vix_level=25.0)
        params = get_optimal_trade_params(f)
        assert isinstance(params, TradeParams)


# ---------------------------------------------------------------------------
# _estimate_features_from_trade
# ---------------------------------------------------------------------------


class TestEstimateFeatures:
    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_extracts_hour(self):
        learner = GRPOTradeLearner()
        trade = {"symbol": "SPY260227P00655000", "filled_at": "2026-02-20T14:30:00Z"}
        features = learner._estimate_features_from_trade(trade, "2026-02-20")
        # hour_int=14, normalized = (14 - 9.5) / 6.5 = ~0.692
        assert 0.6 < features.hour_of_day < 0.8

    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_extracts_day_of_week(self):
        learner = GRPOTradeLearner()
        trade = {"symbol": "SPY260227P00655000", "filled_at": "2026-02-20T10:00:00Z"}
        # 2026-02-20 is a Friday => weekday()=4, normalized = 4/4 = 1.0
        features = learner._estimate_features_from_trade(trade, "2026-02-20")
        assert features.day_of_week == pytest.approx(1.0)

    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_extracts_dte_from_symbol(self):
        learner = GRPOTradeLearner()
        # SPY260227 => expiry 2026-02-27, trade date 2026-02-20 => DTE = 7
        trade = {"symbol": "SPY260227P00655000", "filled_at": "2026-02-20T10:00:00Z"}
        features = learner._estimate_features_from_trade(trade, "2026-02-20")
        assert features.days_to_expiry == pytest.approx(7.0)

    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_defaults_on_short_timestamp(self):
        learner = GRPOTradeLearner()
        trade = {"symbol": "SPY260227P00655000", "filled_at": "2026-02-20"}
        features = learner._estimate_features_from_trade(trade, "2026-02-20")
        assert features.hour_of_day == 0.5  # default


# ---------------------------------------------------------------------------
# _estimate_params_from_trades
# ---------------------------------------------------------------------------


class TestEstimateParams:
    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_delta_estimation_far_otm(self):
        learner = GRPOTradeLearner()
        # Strike 600 vs SPY ~690 => ~13% OTM => delta 0.10
        trades = [{"symbol": "SPY260227P00600000"}]
        params = learner._estimate_params_from_trades(trades)
        assert params.delta == 0.10

    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_delta_estimation_close_otm(self):
        learner = GRPOTradeLearner()
        # Strike 680 vs SPY ~690 => ~1.4% OTM => delta 0.25
        trades = [{"symbol": "SPY260227P00680000"}]
        params = learner._estimate_params_from_trades(trades)
        assert params.delta == 0.25

    @patch("src.ml.grpo_trade_learner.TORCH_AVAILABLE", False)
    @patch("src.ml.grpo_trade_learner.MODEL_PATH", Path("/nonexistent/model.pt"))
    def test_defaults_on_unparseable_symbol(self):
        learner = GRPOTradeLearner()
        trades = [{"symbol": "BAD"}]
        params = learner._estimate_params_from_trades(trades)
        assert params.delta == 0.15  # default
        assert params.dte == 30  # default
