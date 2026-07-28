from src.ml.grpo_shadow_evaluator import GRPOShadowEvaluator
from src.ml.ml_feature_pipeline import MLFeaturePipeline


def test_ml_feature_pipeline_process_tick(tmp_path):
    shadow_log = tmp_path / "shadow.jsonl"
    evaluator = GRPOShadowEvaluator(shadow_log_path=shadow_log)
    pipeline = MLFeaturePipeline(shadow_evaluator=evaluator)
    
    snapshot = {"vix_level": 19.0, "iv_rank": 55.0}
    res = pipeline.process_tick("SPY", "spy_put_credit", snapshot)
    
    assert res["pipeline_status"] == "OK"
    assert res["symbol"] == "SPY"
    assert res["feature_vector_shape"] == [14]
    assert "shadow_evaluation" in res
