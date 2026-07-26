"""
Tests for research_strategies.py and post_market_analysis.py.

100% coverage of new ML pipeline code:
- VIX regime classification
- Strategy research generation
- Regime-aware Thompson Samplers
- Next-day plan generation
- Trade regime classification
"""

from __future__ import annotations

from scripts.post_market_analysis import (
    classify_trade_regime,
    generate_next_day_plan,
    update_regime_thompson_samplers,
)
from scripts.research_strategies import (
    analyze_spy_options_chain,
    analyze_vix_regime,
    generate_daily_research_lesson,
)

# --- VIX Regime Classification ---


def test_vix_regime_calm():
    data = {"data": [[0, 12.5]]}
    result = analyze_vix_regime(data)
    assert result["regime"] == "calm"
    assert result["vix"] == 12.5
    assert "thin" in result["guidance"].lower()


def test_vix_regime_normal():
    data = {"data": [[0, 17.0]]}
    result = analyze_vix_regime(data)
    assert result["regime"] == "normal"
    assert "optimal" in result["guidance"].lower()


def test_vix_regime_elevated():
    data = {"data": [[0, 22.0]]}
    result = analyze_vix_regime(data)
    assert result["regime"] == "elevated"
    assert "rich" in result["guidance"].lower() or "ideal" in result["guidance"].lower()


def test_vix_regime_volatile():
    data = {"data": [[0, 27.0]]}
    result = analyze_vix_regime(data)
    assert result["regime"] == "volatile"
    assert "reduce" in result["guidance"].lower() or "3%" in result["guidance"]


def test_vix_regime_spike():
    data = {"data": [[0, 35.0]]}
    result = analyze_vix_regime(data)
    assert result["regime"] == "spike"
    assert "do not" in result["guidance"].lower()


def test_vix_regime_no_data():
    result = analyze_vix_regime(None)
    assert result["regime"] == "unknown"


def test_vix_regime_empty_data():
    result = analyze_vix_regime({"data": []})
    assert result["regime"] == "unknown"


def test_vix_trend_rising():
    data = {"data": [[0, 15], [1, 16], [2, 17], [3, 18], [4, 20]]}
    result = analyze_vix_regime(data)
    assert result["vix_trend"] == "rising"


def test_vix_trend_falling():
    data = {"data": [[0, 25], [1, 23], [2, 21], [3, 19], [4, 17]]}
    result = analyze_vix_regime(data)
    assert result["vix_trend"] == "falling"


def test_vix_regime_cboe_dict_rows():
    data = {
        "data": [
            {"date": "2026-06-29", "close": "19.5"},
            {"date": "2026-06-30", "close": "18.0"},
            {"date": "2026-07-01", "close": "17.0"},
            {"date": "2026-07-02", "close": "16.0"},
            {"date": "2026-07-03", "close": "14.0"},
        ]
    }
    result = analyze_vix_regime(data)
    assert result["regime"] == "calm"
    assert result["vix"] == 14.0
    assert result["vix_5d_ago"] == 19.5
    assert result["vix_trend"] == "falling"


# --- SPY Options Chain Analysis ---


def test_spy_chain_no_data():
    result = analyze_spy_options_chain(None)
    assert result["status"] == "unavailable"


def test_spy_chain_empty_result():
    result = analyze_spy_options_chain({"optionChain": {"result": []}})
    assert result["status"] == "no_data"


def test_spy_chain_with_quote():
    chain = {
        "optionChain": {
            "result": [
                {
                    "quote": {"regularMarketPrice": 656.50},
                    "expirationDates": [],
                }
            ]
        }
    }
    result = analyze_spy_options_chain(chain)
    assert result["status"] == "ok"
    assert result["spy_price"] == 656.50


# --- Research Lesson Generation ---


def test_research_lesson_contains_regime():
    vix = {"vix": 22.0, "regime": "elevated", "guidance": "Rich premiums", "vix_trend": "falling"}
    chain = {"spy_price": 656.50}
    lesson = generate_daily_research_lesson(vix, chain)
    assert "elevated" in lesson.lower()
    assert "656.5" in lesson
    assert "Delta" in lesson


# --- Trade Regime Classification ---


def test_classify_trade_with_vix_trace():
    trade = {"decision_trace": {"market_context": {"vix": 22.5}}}
    assert classify_trade_regime(trade) == "elevated"


def test_classify_trade_with_high_vix():
    trade = {"decision_trace": {"market_context": {"vix": 35.0}}}
    assert classify_trade_regime(trade) == "spike"


def test_classify_trade_no_trace_high_credit():
    trade = {"entry_credit": 350}
    assert classify_trade_regime(trade) == "volatile"


def test_classify_trade_no_trace_low_credit():
    trade = {"credit_received": 80}
    assert classify_trade_regime(trade) == "calm"


def test_classify_trade_no_data():
    assert classify_trade_regime({}) == "calm"


# --- Regime-Aware Thompson Samplers ---


def test_regime_samplers_from_trades():
    trades_data = {
        "trades": [
            {
                "status": "closed",
                "outcome": "win",
                "decision_trace": {"market_context": {"vix": 17}},
            },
            {
                "status": "closed",
                "outcome": "win",
                "decision_trace": {"market_context": {"vix": 18}},
            },
            {
                "status": "closed",
                "outcome": "loss",
                "decision_trace": {"market_context": {"vix": 16}},
            },
            {
                "status": "closed",
                "outcome": "loss",
                "decision_trace": {"market_context": {"vix": 28}},
            },
            {
                "status": "closed",
                "outcome": "loss",
                "decision_trace": {"market_context": {"vix": 29}},
            },
        ]
    }
    model = {}
    result = update_regime_thompson_samplers(trades_data, model)

    assert "regime_samplers" in result
    # Normal regime: 2W/1L = 66.7%
    assert result["regime_samplers"]["normal"]["wins"] == 2
    assert result["regime_samplers"]["normal"]["losses"] == 1
    assert result["regime_samplers"]["normal"]["win_rate_pct"] == 66.7
    # Volatile regime: 0W/2L = 0%
    assert result["regime_samplers"]["volatile"]["wins"] == 0
    assert result["regime_samplers"]["volatile"]["losses"] == 2


def test_regime_samplers_empty_trades():
    model = {}
    result = update_regime_thompson_samplers({"trades": []}, model)
    assert result["regime_samplers"]["calm"]["total"] == 0


def test_regime_sampler_should_trade_threshold():
    trades = {
        "trades": [
            {
                "status": "closed",
                "outcome": "win",
                "decision_trace": {"market_context": {"vix": 17}},
            }
            for _ in range(8)
        ]
        + [
            {
                "status": "closed",
                "outcome": "loss",
                "decision_trace": {"market_context": {"vix": 17}},
            }
            for _ in range(2)
        ]
    }
    model = {}
    result = update_regime_thompson_samplers(trades, model)
    # 8W/2L = 80%, 10 trades >= 10 minimum -> should_trade = True
    assert result["regime_samplers"]["normal"]["should_trade"] is True


def test_regime_sampler_blocks_low_sample():
    trades = {
        "trades": [
            {
                "status": "closed",
                "outcome": "win",
                "decision_trace": {"market_context": {"vix": 17}},
            }
            for _ in range(5)
        ]
    }
    model = {}
    result = update_regime_thompson_samplers(trades, model)
    # 5W/0L = 100% but only 5 trades < 10 minimum -> should_trade = False
    assert result["regime_samplers"]["normal"]["should_trade"] is False


# --- Next Day Plan Generation ---


def test_plan_trade_when_all_gates_pass():
    model = {
        "regime_samplers": {"normal": {"should_trade": True, "win_rate_pct": 75, "total": 20}},
        "gate": {"should_trade": True},
    }
    research = {
        "recommendations": {
            "regime": "normal",
            "should_trade": True,
            "suggested_delta": 15,
            "suggested_profit_target": 0.50,
        }
    }
    plan = generate_next_day_plan(model, research)
    assert plan["action"] == "TRADE"
    assert plan["suggested_delta"] == 15


def test_plan_hold_when_regime_blocks():
    model = {
        "regime_samplers": {"volatile": {"should_trade": False, "win_rate_pct": 20, "total": 15}},
        "gate": {"should_trade": True},
    }
    research = {
        "recommendations": {
            "regime": "volatile",
            "should_trade": True,
            "suggested_delta": 10,
            "suggested_profit_target": 0.25,
        }
    }
    plan = generate_next_day_plan(model, research)
    assert plan["action"] == "HOLD"
    assert any("win rate" in r.lower() for r in plan["hold_reasons"])


def test_plan_hold_when_research_blocks():
    model = {
        "regime_samplers": {"spike": {"should_trade": False, "win_rate_pct": 0, "total": 0}},
        "gate": {"should_trade": True},
    }
    research = {"recommendations": {"regime": "spike", "should_trade": False}}
    plan = generate_next_day_plan(model, research)
    assert plan["action"] == "HOLD"


def test_plan_hold_when_global_gate_blocks():
    model = {
        "regime_samplers": {"normal": {"should_trade": True, "win_rate_pct": 80, "total": 30}},
        "gate": {"should_trade": False, "block_reason": "Win rate 24.2% < 50.0%"},
    }
    research = {"recommendations": {"regime": "normal", "should_trade": True}}
    plan = generate_next_day_plan(model, research)
    assert plan["action"] == "HOLD"
    assert any("global gate" in r.lower() for r in plan["hold_reasons"])
