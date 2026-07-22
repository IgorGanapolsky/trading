"""Tests for the evidence-first strategy pivot gate."""

from __future__ import annotations

from src.safety.strategy_pivot import (
    BrokerSnapshot,
    StrategyEvidence,
    ValidationThresholds,
    assess_broker,
    audit_strategy_ledger,
    build_pivot_report,
    evaluate_strategy,
)


def _state() -> dict:
    return {
        "paper_account": {
            "starting_balance": 100_000.0,
            "equity": 94_062.0,
            "total_pl": -5_938.0,
            "total_pl_pct": -5.938,
        },
        "performance": {
            "open_positions": [
                {"symbol": "SPY260821C00776000", "quantity": -2},
                {"symbol": "SPY260821C00781000", "quantity": 2},
                {"symbol": "SPY260821P00695000", "quantity": 1},
                {"symbol": "SPY260821P00700000", "quantity": -1},
                {"symbol": "SPY260821P00703000", "quantity": 1},
                {"symbol": "SPY260821P00708000", "quantity": -1},
            ]
        },
        "north_star_weekly_gate": {
            "lifetime_ledger": {
                "closed_trades": 174,
                "expectancy_per_trade": -31.977,
                "profit_factor": 0.70,
                "total_realized_pnl": -5_564.0,
            }
        },
    }


def _trades() -> dict:
    return {
        "stats": {
            "closed_trades": 174,
            "unpaired_order_count": 15,
        },
        "trades": [{} for _ in range(159)],
    }


def _broker() -> dict:
    return {
        "broker": "clearstreet_active",
        "observed_at": "2026-07-22T16:31:00-04:00",
        "account": {
            "authenticated_web_session": True,
            "funded": False,
            "equity_usd": 0,
            "api_key_configured": False,
            "options_level": 0,
        },
        "api_capabilities": {
            "market_data": True,
            "equities": True,
            "single_leg_options": True,
            "multi_leg_options": False,
            "paper_trading_verified": False,
        },
    }


def test_ledger_audit_detects_unpaired_and_overwritten_same_expiry_entry() -> None:
    audit = audit_strategy_ledger(
        _state(),
        _trades(),
        {"IC_260821": {"order_id": "second-entry-overwrote-first"}},
    )

    assert not audit.clean
    assert audit.unpaired_order_count == 15
    assert any("unpaired orders" in issue for issue in audit.issues)
    assert any("represents 2 structures" in issue for issue in audit.issues)


def test_negative_mature_incumbent_is_retired_but_exits_remain_allowed() -> None:
    audit = audit_strategy_ledger(_state(), _trades(), {"IC_260821": {}})
    decision = evaluate_strategy(
        StrategyEvidence(
            closed_trades=174,
            expectancy_per_trade=-31.98,
            profit_factor=0.70,
            total_realized_pnl=-5_564,
            max_drawdown_pct=5.94,
        ),
        audit,
    )

    assert decision.status == "RETIRE_NEW_ENTRIES"
    assert not decision.may_open_new_positions
    assert decision.may_manage_existing_positions


def test_clean_candidate_needs_30_trades_and_positive_edge() -> None:
    clean_audit = audit_strategy_ledger(
        {"performance": {"open_positions": []}},
        {"stats": {"closed_trades": 30, "unpaired_order_count": 0}, "trades": [{}] * 30},
        {},
    )
    decision = evaluate_strategy(
        StrategyEvidence(
            closed_trades=30,
            expectancy_per_trade=12.0,
            profit_factor=1.25,
            total_realized_pnl=360.0,
            max_drawdown_pct=4.0,
        ),
        clean_audit,
        ValidationThresholds(),
    )

    assert decision.status == "PAPER_VALIDATED"
    assert decision.may_open_new_positions


def test_clearstreet_is_research_only_and_cannot_execute_iron_condor() -> None:
    snapshot = BrokerSnapshot.from_payload(_broker())
    assessment = assess_broker(
        snapshot,
        {
            "asset_class": "option",
            "legs": 4,
            "minimum_options_level": 3,
            "requires_paper_trading": True,
        },
    )

    assert assessment.research_eligible
    assert not assessment.execution_eligible
    assert "No broker API key is configured." in assessment.blockers
    assert "The API does not support atomic multi-leg option execution." in assessment.blockers


def test_report_stays_exit_only_until_a_candidate_passes() -> None:
    tournament = {
        "incumbent_strategy_id": "ic_simple",
        "promotion_thresholds": {},
        "candidates": [
            {
                "strategy_id": "spy_long_trend",
                "hypothesis": "test",
                "rules": {},
                "broker_requirements": {
                    "asset_class": "equity",
                    "legs": 1,
                    "requires_paper_trading": True,
                },
                "evidence": {
                    "closed_trades": 0,
                    "expectancy_per_trade": 0,
                    "profit_factor": 0,
                    "total_realized_pnl": 0,
                    "ledger_clean": True,
                },
            }
        ],
    }

    report = build_pivot_report(_state(), _trades(), {"IC_260821": {}}, tournament, _broker())

    assert report["system_action"] == "RECONCILE_INVENTORY_MANAGE_EXITS_ONLY"
    assert not report["north_star"]["on_course"]
    assert report["incumbent"]["decision"]["status"] == "RETIRE_NEW_ENTRIES"
    assert report["candidates"][0]["decision"]["status"] == "PAPER_VALIDATION_ONLY"
    assert report["broker"]["current_role"] == "RESEARCH_ONLY"


def test_report_runs_successor_cohort_when_broker_inventory_is_reconstructed() -> None:
    tournament = {
        "incumbent_strategy_id": "ic_simple",
        "active_paper_candidate_id": "spy_put_credit",
        "promotion_thresholds": {},
        "candidates": [
            {
                "strategy_id": "spy_put_credit",
                "hypothesis": "test",
                "rules": {},
                "broker_requirements": {
                    "asset_class": "option",
                    "legs": 2,
                    "minimum_options_level": 3,
                    "requires_paper_trading": True,
                },
                "evidence": {
                    "closed_trades": 0,
                    "expectancy_per_trade": 0,
                    "profit_factor": 0,
                    "total_realized_pnl": 0,
                    "ledger_clean": True,
                },
            }
        ],
    }
    inventory = {
        "clean": True,
        "authority": "broker_filled_mleg_orders",
        "audited_at": "2026-07-22T21:39:36+00:00",
        "reconstruction": {
            "recovered_ic_structures": 2,
            "unresolved": {},
            "pending_option_orders": 0,
        },
    }

    report = build_pivot_report(
        _state(), _trades(), {"IC_260821": {}}, tournament, _broker(), inventory
    )

    assert report["system_action"] == "RETIRE_INCUMBENT_PAPER_VALIDATE_SUCCESSOR"
    assert report["research_action"] == "RUN_ACTIVE_SUCCESSOR_PAPER_COHORT"
    assert report["operational_inventory"]["clean"] is True
    assert report["incumbent"]["ledger_audit"]["clean"] is False
    assert report["north_star"]["on_course"] is False
