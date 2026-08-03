from scripts.world_class_trading_readiness import build_readiness


def test_world_class_readiness_separates_engineering_from_money_proof() -> None:
    report = build_readiness(include_rag_eval=False)

    goal = report["goal_contract"]
    rag = report["rag_evidence"]
    verdicts = report["verdicts"]

    assert goal["monthly_after_tax_target_usd"] == 1000.0
    assert goal["required_realized_pretax_monthly_usd"] == 1587.3
    assert goal["target_consistent_across_runtime_state"] is True
    assert rag["health"]["quality_pass_rate"] == 1.0
    assert rag["ingestion"]["rejected"] == rag["governance_quarantined"]
    assert verdicts["live_capital_ready"] is False
    assert verdicts["monthly_after_tax_goal_proven"] is False
    assert verdicts["world_class_system_ready"] is False
    assert report["profit_outcome"]["claim_allowed"] is False
