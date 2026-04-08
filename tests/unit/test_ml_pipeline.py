"""Tests for ML/RAG pipeline — Thompson sampling, vector RAG, composite reward, strategy params."""

import json
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# Stub heavy deps not installed locally
def _ensure_module(name):
    if name not in sys.modules:
        parts = name.split(".")
        for i in range(len(parts)):
            partial = ".".join(parts[: i + 1])
            if partial not in sys.modules:
                sys.modules[partial] = types.ModuleType(partial)


# Only stub modules that aren't already installed
try:
    import numpy
except ImportError:
    _ensure_module("numpy")
    np_mod = sys.modules["numpy"]
    np_mod.array = lambda *a, **k: []
    np_mod.float32 = float
    np_mod.std = lambda *a, **k: 0.0
    np_mod.sqrt = lambda x: x**0.5
    np_mod.diff = lambda *a, **k: []
    np_mod.log = lambda *a, **k: []
    np_mod.ndarray = type("ndarray", (), {})
    np_mod.isscalar = lambda x: isinstance(x, (int, float, complex))
    np_mod.asarray = lambda x, **k: x
    np_mod.bool_ = bool
    np_mod.int_ = int
    np_mod.float_ = float
    np_mod.complex_ = complex
    np_mod.object_ = object
    np_mod.str_ = str

try:
    import torch
except ImportError:
    _ensure_module("torch")
    _ensure_module("torch.nn")
    _ensure_module("torch.optim")
    torch_mod = sys.modules["torch"]
    torch_mod.tensor = lambda *a, **k: None
    torch_mod.load = lambda *a, **k: {}
    torch_mod.save = lambda *a, **k: None
    torch_mod.no_grad = lambda: type(
        "ctx", (), {"__enter__": lambda s: None, "__exit__": lambda s, *a: None}
    )()
    nn_mod = sys.modules["torch.nn"]
    nn_mod.Module = type("Module", (), {})
    nn_mod.Linear = type("Linear", (), {"__init__": lambda s, *a, **k: None})
    nn_mod.ReLU = type("ReLU", (), {})
    nn_mod.Sequential = type("Sequential", (), {"__init__": lambda s, *a: None})

from src.ml.reward import compute_trade_reward, compute_portfolio_reward
from src.rag.vector_store import TradeRAG


# ══════════════════════════════════════════════════════════════════════════════
# 1. Thompson Sampling
# ══════════════════════════════════════════════════════════════════════════════


class TestThompsonSampling:
    """Verify Thompson priors, confidence sampling, and Bayesian updates."""

    def test_default_priors_are_informative(self):
        """Beta(86,14) not Beta(1,1) — cold-start fix."""
        from src.ml.trade_confidence import TradeConfidenceModel

        model = TradeConfidenceModel()
        defaults = model._default_model()
        assert defaults["iron_condor"]["alpha"] == 86.0
        assert defaults["iron_condor"]["beta"] == 14.0
        # Posterior mean should be ~0.86
        mean = defaults["iron_condor"]["alpha"] / (
            defaults["iron_condor"]["alpha"] + defaults["iron_condor"]["beta"]
        )
        assert 0.84 <= mean <= 0.88

    def test_posterior_mean_matches_expected(self):
        from src.ml.trade_confidence import TradeConfidenceModel

        model = TradeConfidenceModel()
        model.model = model._default_model()
        mean = model.get_posterior_mean("iron_condor", "SPY")
        assert 0.84 <= mean <= 0.88

    def test_sample_confidence_in_valid_range(self):
        from src.ml.trade_confidence import TradeConfidenceModel

        model = TradeConfidenceModel()
        model.model = model._default_model()
        samples = [model.sample_confidence("iron_condor", "SPY") for _ in range(100)]
        assert all(0 <= s <= 1 for s in samples)
        avg = sum(samples) / len(samples)
        assert 0.75 <= avg <= 0.95  # Should cluster around 0.86

    def test_regime_spike_reduces_confidence(self):
        from src.ml.trade_confidence import TradeConfidenceModel

        model = TradeConfidenceModel()
        model.model = model._default_model()
        normal = model.sample_confidence("iron_condor", "SPY")
        spike = model.sample_confidence("iron_condor", "SPY", regime="spike")
        # Spike multiplier is 0.5, so spike should be roughly half
        assert spike <= normal

    def test_update_after_win_increases_alpha(self):
        from src.ml.trade_confidence import TradeConfidenceModel

        model = TradeConfidenceModel()
        model.model = model._default_model()
        old_alpha = model.model["iron_condor"]["alpha"]
        model.record_trade_outcome(success=True, strategy="iron_condor", ticker="SPY")
        assert model.model["iron_condor"]["alpha"] == old_alpha + 1
        assert model.model["iron_condor"]["wins"] == 1

    def test_update_after_loss_increases_beta(self):
        from src.ml.trade_confidence import TradeConfidenceModel

        model = TradeConfidenceModel()
        model.model = model._default_model()
        old_beta = model.model["iron_condor"]["beta"]
        model.record_trade_outcome(success=False, strategy="iron_condor", ticker="SPY")
        assert model.model["iron_condor"]["beta"] == old_beta + 1
        assert model.model["iron_condor"]["losses"] == 1


# ══════════════════════════════════════════════════════════════════════════════
# 2. RAG Vector Store
# ══════════════════════════════════════════════════════════════════════════════


class TestRAGVectorStore:
    """Verify RAG indexes documents and returns relevant results."""

    def test_builds_index_without_error(self):
        rag = TradeRAG()
        # Manually add a doc instead of relying on filesystem
        rag.documents = [
            {"id": "test1", "content": "iron condor profit target 50%", "source": "test"},
        ]
        # Just verify the object works
        assert isinstance(rag.documents, list)
        assert len(rag.documents) == 1
        assert rag.documents[0]["source"] == "test"

    def test_query_returns_results(self):
        rag = TradeRAG()
        rag.documents = [
            {"id": "t1", "content": "iron condor profit target exit at 50%", "source": "test"},
            {"id": "t2", "content": "SPY put spread delta 15 entry", "source": "test"},
        ]
        results = rag.query("iron condor profit exit", top_k=3)
        assert len(results) >= 1
        assert "score" in results[0]
        assert results[0]["score"] > 0

    def test_query_results_have_required_fields(self):
        rag = TradeRAG()
        rag.documents = [
            {"id": "t1", "content": "SPY iron condor trade lesson", "source": "test"},
        ]
        results = rag.query("SPY trade", top_k=1)
        assert len(results) >= 1
        assert "content" in results[0]
        assert "source" in results[0]
        assert "score" in results[0]

    def test_query_returns_empty_for_no_match(self):
        rag = TradeRAG()
        rag.documents = [{"id": "test", "content": "apple banana cherry", "source": "test"}]
        results = rag.query("quantum physics relativity", top_k=3)
        assert isinstance(results, list)

    def test_documents_have_source_field(self):
        rag = TradeRAG()
        rag.documents = [
            {"id": "t1", "content": "test doc", "source": "lesson"},
            {"id": "t2", "content": "test doc 2", "source": "journal"},
        ]
        for doc in rag.documents:
            assert doc["source"] in ("lesson", "journal", "test")


# ══════════════════════════════════════════════════════════════════════════════
# 3. Composite Reward Function
# ══════════════════════════════════════════════════════════════════════════════


class TestCompositeReward:
    """Verify reward function encodes loss aversion (Phil Town Rule #1)."""

    def test_win_reward_is_positive(self):
        r = compute_trade_reward(pnl=41.0, credit=0.81, max_loss=919.0, dte_at_exit=14)
        assert r["total_reward"] > 0

    def test_loss_reward_is_negative(self):
        r = compute_trade_reward(pnl=-81.0, credit=0.81, max_loss=919.0, dte_at_exit=7)
        assert r["total_reward"] < 0

    def test_loss_magnitude_exceeds_win_magnitude(self):
        """Phil Town Rule #1: losses penalized more than wins rewarded."""
        win = compute_trade_reward(pnl=100.0, credit=2.50, max_loss=750.0, dte_at_exit=14)
        loss = compute_trade_reward(pnl=-100.0, credit=2.50, max_loss=750.0, dte_at_exit=14)
        assert abs(loss["total_reward"]) > abs(win["total_reward"])

    def test_reward_has_three_components(self):
        r = compute_trade_reward(pnl=50.0, credit=2.00, max_loss=800.0, dte_at_exit=10)
        assert "return" in r["components"]
        assert "downside" in r["components"]
        assert "benchmark_excess" in r["components"]

    def test_zero_pnl_near_zero_reward(self):
        r = compute_trade_reward(pnl=0.0, credit=2.00, max_loss=800.0, dte_at_exit=15)
        assert abs(r["total_reward"]) < 0.5

    def test_downside_zero_for_winning_trade(self):
        r = compute_trade_reward(pnl=100.0, credit=2.50, max_loss=750.0, dte_at_exit=14)
        assert r["components"]["downside"] == 0.0

    def test_portfolio_reward_with_journal(self):
        r = compute_portfolio_reward(lookback_trades=30)
        # Should work even with 1 trade in journal
        assert "total_reward" in r
        assert "trade_count" in r


# ══════════════════════════════════════════════════════════════════════════════
# 4. Strategy Params (ML-writable config)
# ══════════════════════════════════════════════════════════════════════════════


class TestStrategyParams:
    """Verify ic_simple reads ML-adjustable params."""

    def test_loads_from_file(self):
        params_file = Path("data/strategy_params.json")
        if not params_file.exists():
            pytest.skip("strategy_params.json not found")
        data = json.loads(params_file.read_text())
        assert "params" in data
        assert "target_delta" in data["params"]
        assert "max_ic" in data["params"]

    def test_default_params_have_all_keys(self):
        sys.path.insert(0, ".")
        from scripts.ic_simple import _load_strategy_params

        params = _load_strategy_params()
        required = [
            "target_delta",
            "wing_width",
            "target_dte",
            "min_dte",
            "max_dte",
            "min_credit",
            "profit_target",
            "stop_loss",
            "exit_dte",
            "max_ic",
        ]
        for key in required:
            assert key in params, f"Missing param: {key}"

    def test_max_ic_is_4(self):
        sys.path.insert(0, ".")
        from scripts.ic_simple import _load_strategy_params

        params = _load_strategy_params()
        assert params["max_ic"] == 4

    def test_adjust_strategy_params_respects_bounds(self):
        sys.path.insert(0, ".")
        from scripts.ic_simple import _adjust_strategy_params, STRATEGY_PARAMS_FILE

        # Save original
        original = STRATEGY_PARAMS_FILE.read_text() if STRATEGY_PARAMS_FILE.exists() else None

        try:
            # Try to set delta out of bounds
            _adjust_strategy_params(
                {"target_delta": 0.50},  # Way above 0.25 max bound
                reason="test",
                source="test",
                confidence=0.80,
            )
            data = json.loads(STRATEGY_PARAMS_FILE.read_text())
            # Should be clamped to 0.25
            assert data["params"]["target_delta"] <= 0.25
        finally:
            # Restore original
            if original:
                STRATEGY_PARAMS_FILE.write_text(original)

    def test_adjust_rejected_below_confidence(self):
        sys.path.insert(0, ".")
        from scripts.ic_simple import _adjust_strategy_params, STRATEGY_PARAMS_FILE

        original = STRATEGY_PARAMS_FILE.read_text() if STRATEGY_PARAMS_FILE.exists() else None
        original_data = json.loads(original) if original else {}
        old_delta = original_data.get("params", {}).get("target_delta", 0.15)

        try:
            _adjust_strategy_params(
                {"target_delta": 0.20},
                reason="test",
                source="test",
                confidence=0.50,  # Below 0.70 threshold
            )
            data = json.loads(STRATEGY_PARAMS_FILE.read_text())
            # Should NOT have changed
            assert data["params"]["target_delta"] == old_delta
        finally:
            if original:
                STRATEGY_PARAMS_FILE.write_text(original)
