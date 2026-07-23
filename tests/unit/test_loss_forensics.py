"""Tests for loss forensics + misery diagnosis (DS root-cause layer)."""

from __future__ import annotations

from src.analytics.loss_forensics import (
    analyze_loss_clusters,
    build_system_diagnosis,
    strategy_family,
    wing_width,
)
from src.ml.trade_confidence import TradeConfidenceModel
from src.rag.context_repositioning import reposition_lessons


def test_wing_width_from_structured_legs_and_trade_id():
    trade = {
        "id": "IC_SPY_2026_04_10_P630_640_C705_715_x",
        "legs": {"put_strikes": [630.0, 640.0], "call_strikes": [705.0, 715.0]},
    }
    assert wing_width(trade) == 10.0


def test_wing_width_from_trade_id_only():
    trade = {"id": "IC_SPY_2026_08_14_P690_695_C774_779_abc", "legs": None}
    assert wing_width(trade) == 5.0


def test_strategy_family_put_credit_aliases():
    assert strategy_family({"strategy": "spy_put_credit"}) == "spy_put_credit"
    assert strategy_family({"strategy": "bull_put"}) == "spy_put_credit"
    assert strategy_family({"strategy": "iron_condor"}) == "iron_condor"
    assert strategy_family({"id": "IC_SPY_2026_01_01"}) == "iron_condor"


def test_loss_clusters_detect_ten_wide_and_multi_lot():
    trades = {
        "trades": [
            {
                "id": "wide",
                "strategy": "iron_condor",
                "outcome": "loss",
                "realized_pnl": -100,
                "quantity": 2,
                "entry_time": "2026-04-01T14:00:00+00:00",
                "exit_time": "2026-04-01T14:20:00+00:00",
                "legs": {"put_strikes": [630, 640], "call_strikes": [705, 715]},
            },
            {
                "id": "narrow",
                "strategy": "iron_condor",
                "outcome": "win",
                "realized_pnl": 25,
                "quantity": 1,
                "entry_time": "2026-04-04T14:00:00+00:00",
                "exit_time": "2026-04-05T15:00:00+00:00",
                "legs": {"put_strikes": [620, 625], "call_strikes": [700, 705]},
            },
        ]
    }
    clusters = {c["id"]: c for c in analyze_loss_clusters(trades)}
    assert clusters["ten_wide_wings"]["sample_size"] == 1
    assert clusters["multi_contract"]["sample_size"] == 1
    assert clusters["early_exit_lt_1h"]["sample_size"] == 1


def test_build_system_diagnosis_headline_and_successor_gap():
    trades = {
        "stats": {
            "closed_trades": 2,
            "wins": 0,
            "losses": 2,
            "win_rate_pct": 0.0,
            "profit_factor": 0.0,
            "total_realized_pnl": -150.0,
            "expectancy": -75.0,
        },
        "trades": [
            {
                "id": "IC_A_P600_610_C700_710",
                "strategy": "iron_condor",
                "outcome": "loss",
                "realized_pnl": -100,
                "quantity": 2,
                "entry_time": "2026-03-01T14:00:00+00:00",
                "exit_time": "2026-03-01T15:00:00+00:00",
                "legs": {"put_strikes": [600, 610], "call_strikes": [700, 710]},
            },
            {
                "id": "IC_B_P600_610_C700_710",
                "strategy": "iron_condor",
                "outcome": "loss",
                "realized_pnl": -50,
                "quantity": 1,
                "entry_time": "2026-03-02T14:00:00+00:00",
                "exit_time": "2026-03-02T16:00:00+00:00",
                "legs": {"put_strikes": [600, 610], "call_strikes": [700, 710]},
            },
        ],
    }
    diagnosis = build_system_diagnosis(trades, active_family="spy_put_credit")
    assert "miserable" in diagnosis["headline"].lower()
    cause_ids = {c["id"] for c in diagnosis["root_causes"]}
    assert "successor_not_sampled" in cause_ids
    assert diagnosis["north_star"]["on_track"] is False
    assert diagnosis["ledger"]["views"]["reconciles"] is True
    assert "paired closed structures only" in diagnosis["ledger"]["views"]["note"]
    assert "paired + unpaired fold" not in diagnosis["ledger"]["views"]["note"]
    assert any("put-credit" in a.lower() or "spy_put_credit" in a for a in diagnosis["operator_actions"])


def test_put_credit_confidence_not_poisoned_by_ic_spy_specific():
    model = TradeConfidenceModel()
    model.model = {
        "iron_condor": {"alpha": 31.0, "beta": 146.0, "wins": 30, "losses": 145},
        "spy_specific": {"alpha": 31.0, "beta": 146.0, "wins": 30, "losses": 145},
        "spy_put_credit": {"alpha": 1.0, "beta": 1.0, "wins": 0, "losses": 0},
        "regime_adjustments": {},
        "active_family": "spy_put_credit",
    }
    # Put credit on SPY must NOT use spy_specific IC posterior (~17%)
    put_mean = model.get_posterior_mean("spy_put_credit", "SPY")
    ic_mean = model.get_posterior_mean("iron_condor", "SPY")
    assert abs(put_mean - 0.5) < 1e-9
    assert ic_mean < 0.25


def test_rag_reposition_boosts_misery_forensics_lessons():
    lessons = [
        {
            "id": "unrelated_blog",
            "title": "Weekly market notes",
            "content": "SPY bounced. No root cause analysis.",
            "score": 0.9,
            "severity": "LOW",
        },
        {
            "id": "system_misery_diagnosis_current",
            "title": "System Misery Diagnosis",
            "content": (
                "## Root Cause\nLoss clusters: ten_wide_wings, multi_contract, early_exit. "
                "IC Simple killed. Profit factor 0.7. Expectancy negative. North star blocked."
            ),
            "score": 0.2,
            "severity": "CRITICAL",
        },
    ]
    ranked = reposition_lessons("why are we losing money and failing north star?", lessons, top_k=2)
    assert ranked[0]["id"] == "system_misery_diagnosis_current"
