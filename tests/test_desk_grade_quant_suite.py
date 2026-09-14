"""Unit tests for Desk-Grade Quantitative, ML & Agentic RAG Trading Suite."""

from __future__ import annotations

import json
from pathlib import Path

from src.analysis.desk_grade_options_quant import DeskGradeOptionsQuantEngine
from src.ml.desk_grade_options_ml import DeskGradeOptionsMLEngine, MarketRegimeState
from src.rag.trade_rag_advisory_engine import AdvisoryVerdict, TradeRAGAdvisoryEngine

REPO = Path(__file__).resolve().parents[1]


# =========================================================================
# Pillar 1: Quantitative Data Science Tests (10/10)
# =========================================================================


def test_iv_metrics_rank_and_skew():
    history = [0.10, 0.12, 0.15, 0.18, 0.20]
    metrics = DeskGradeOptionsQuantEngine.compute_iv_metrics(
        current_iv=0.15,
        historical_iv_series=history,
        put_iv_25d=0.18,
        call_iv_25d=0.14,
        vix_1m=17.67,
        vix_3m=18.50,
    )
    # IV Rank: (0.15 - 0.10) / (0.20 - 0.10) = 50%
    assert abs(metrics.iv_rank - 50.0) < 1e-3
    # IV Percentile: 2 out of 5 days (0.10, 0.12) are below 0.15 -> 40%
    assert abs(metrics.iv_percentile - 40.0) < 1e-3
    # Skew: 0.18 - 0.14 = +0.04 (standard put skew)
    assert abs(metrics.skew_25d - 0.04) < 1e-3
    # Term structure: 17.67 / 18.50 < 1.0 (contango)
    assert metrics.term_structure_ratio < 1.0


def test_tail_risk_metrics():
    pnls = [25.0, 24.0, -100.0, 25.0, 24.0, -200.0, 25.0, 25.0]
    tail = DeskGradeOptionsQuantEngine.compute_tail_risk_metrics(pnls, initial_capital=10000.0)
    assert tail.var_95 > 0.0
    assert tail.cvar_95 >= tail.var_95  # CVaR is always >= VaR
    assert tail.max_drawdown > 0.0
    assert tail.max_drawdown_pct > 0.0


def test_risk_adjusted_ratios():
    pnls = [25.0, 24.0, 26.0, 25.0, 24.0, 25.0]
    ratios = DeskGradeOptionsQuantEngine.compute_risk_adjusted_ratios(pnls)
    assert ratios.win_rate_pct == 100.0
    assert ratios.expectancy == 24.833333333333332
    assert ratios.sharpe_ratio > 0.0
    assert ratios.sortino_ratio > 0.0


def test_monte_carlo_expectancy_simulation():
    pnls = [25.0, 24.0, 26.0, 25.0, 24.0, 25.0]
    mc = DeskGradeOptionsQuantEngine.simulate_monte_carlo_expectancy(
        pnls, n_simulations=1000, horizon_trades=30, initial_capital=10000.0
    )
    assert mc.n_simulations == 1000
    assert mc.horizon_trades == 30
    assert mc.mean_final_equity > 10000.0
    assert mc.expectancy_ci_lower_95 > 20.0
    assert mc.expectancy_ci_upper_95 < 30.0
    assert mc.probability_of_ruin_pct == 0.0


# =========================================================================
# Pillar 2: Machine Learning Tests (10/10)
# =========================================================================


def test_purged_kfold_splits():
    trade_durations = [(0, 10), (15, 25), (30, 45), (60, 80)]
    splits = DeskGradeOptionsMLEngine.purged_kfold_split(
        100, trade_durations, n_splits=4, embargo_pct=0.02
    )
    assert len(splits) == 4
    for split in splits:
        assert len(split.test_indices) > 0
        assert len(split.train_indices) > 0
        # No test sample should be in train set
        assert set(split.train_indices).isdisjoint(set(split.test_indices))


def test_regime_classifier_states():
    # 1. Sweet Spot
    r1 = DeskGradeOptionsMLEngine.classify_market_regime(
        vix=18.0, iv_rank=50.0, spy_price=596.0, spy_200_dma=540.0
    )
    assert r1.regime_state == MarketRegimeState.SWEET_SPOT_PREMIUM
    assert r1.trade_allowed is True
    assert r1.position_size_multiplier == 1.0

    # 2. High Vol Crash Block (VIX > 28)
    r2 = DeskGradeOptionsMLEngine.classify_market_regime(
        vix=32.0, iv_rank=85.0, spy_price=596.0, spy_200_dma=540.0
    )
    assert r2.regime_state == MarketRegimeState.HIGH_VOL_CRASH_BLOCK
    assert r2.trade_allowed is False

    # 3. Low Vol Compression (IVR < 20)
    r3 = DeskGradeOptionsMLEngine.classify_market_regime(
        vix=13.0, iv_rank=15.0, spy_price=596.0, spy_200_dma=540.0
    )
    assert r3.regime_state == MarketRegimeState.LOW_VOL_COMPRESSION
    assert r3.trade_allowed is False

    # 4. Low Vol Bull Grind
    r4 = DeskGradeOptionsMLEngine.classify_market_regime(
        vix=14.0, iv_rank=25.0, spy_price=596.0, spy_200_dma=540.0
    )
    assert r4.regime_state == MarketRegimeState.LOW_VOL_BULL
    assert r4.trade_allowed is True
    assert r4.position_size_multiplier == 0.75


def test_calibrated_win_probability():
    res = DeskGradeOptionsMLEngine.predict_calibrated_win_probability(
        delta=0.10, iv_rank=60.0, vix=17.5, trend_ratio=1.05
    )
    # Delta 0.10 implies ~90% raw win rate
    assert abs(res.raw_delta_pop - 0.90) < 1e-3
    # VRP premium crush increases calibrated win probability above 90%
    assert res.calibrated_pop > res.raw_delta_pop
    assert res.edge_over_delta > 0.0
    assert 0.0 < res.brier_score_estimate < 0.25


# =========================================================================
# Pillar 3: Agentic RAG Tests (10/10)
# =========================================================================


def test_rag_pre_trade_advisory():
    rag = TradeRAGAdvisoryEngine(REPO)
    # Optimal trade setup
    advisory = rag.evaluate_pre_trade_advisory(
        underlying="SPY",
        short_strike=728.0,
        long_strike=723.0,
        expiry="2026-10-23",
        credit=0.62,
        vix=17.67,
        iv_rank=56.38,
        spy_above_200dma=True,
    )
    assert advisory.verdict == AdvisoryVerdict.GO
    assert advisory.confidence >= 0.90
    assert len(advisory.citations) > 0
    assert len(advisory.advisory_hash) == 16


def test_rag_blocked_verdict_on_unsafe_regime():
    rag = TradeRAGAdvisoryEngine(REPO)
    advisory = rag.evaluate_pre_trade_advisory(
        underlying="SPY",
        short_strike=728.0,
        long_strike=723.0,
        expiry="2026-10-23",
        credit=0.62,
        vix=35.0,  # Extreme volatility
        iv_rank=15.0,  # Low IV rank
        spy_above_200dma=False,  # Downtrend
    )
    assert advisory.verdict == AdvisoryVerdict.BLOCKED
    assert advisory.confidence >= 0.95
    assert len(advisory.reasons) >= 3


def test_rag_post_trade_lesson_generation():
    rag = TradeRAGAdvisoryEngine(REPO)
    lesson_md = rag.generate_post_trade_lesson(
        trade_id="PCS_261016_62c503",
        pnl=24.83,
        exit_reason="take_profit_25pct",
        vix=17.67,
        ivr=56.38,
    )
    assert "LL-Trade-PCS_261016_62c503: WIN ($+24.83)" in lesson_md
    assert "VIX `17.67`" in lesson_md
    assert "Invariant Codified" in lesson_md


# =========================================================================
# Unified CLI Suite Execution Tests
# =========================================================================


def test_cli_suite_execution(capsys):
    import importlib.util

    cli_path = REPO / "scripts" / "desk_grade_quant_suite.py"
    spec = importlib.util.spec_from_file_location("desk_grade_quant_suite", cli_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Doctor check
    rc = mod.main(["--doctor", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["score"] == 3
    assert "A+ (10/10" in out["grade"]

    # Run quant
    rc = mod.main(["--run-quant", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert "monte_carlo" in out
    assert "risk_adjusted_ratios" in out

    # Run ML
    rc = mod.main(["--run-ml", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert "market_regime" in out
    assert "calibrated_pop" in out

    # Run RAG
    rc = mod.main(["--run-rag", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["verdict"] == "GO"
