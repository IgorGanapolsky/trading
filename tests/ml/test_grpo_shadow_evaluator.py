from src.ml.grpo_shadow_evaluator import GRPOShadowEvaluator, ShadowEvaluation


def test_grpo_shadow_evaluation(tmp_path):
    log_file = tmp_path / "shadow_log.jsonl"
    evaluator = GRPOShadowEvaluator(shadow_log_path=log_file)

    snapshot = {"vix_level": 22.0, "vix_percentile": 0.65, "vix_term_structure": 1.1}
    eval_res = evaluator.evaluate_shadow_tick(
        symbol="SPY",
        strategy="spy_put_credit",
        snapshot=snapshot,
        baseline_delta=0.15,
        baseline_dte=35,
    )

    assert isinstance(eval_res, ShadowEvaluation)
    assert eval_res.symbol == "SPY"
    assert eval_res.strategy == "spy_put_credit"
    assert eval_res.proposed_delta > 0.0
    assert eval_res.proposed_dte > 0
    assert log_file.exists()

    records = evaluator.read_shadow_evaluations()
    assert len(records) == 1
    assert records[0]["symbol"] == "SPY"
