from src.eval.eval_harness import EvalHarness
from src.eval.trace_miner import TraceMiner


def test_trace_miner_generates_cases(tmp_path):
    miner = TraceMiner(trace_dir=tmp_path)
    cases = miner.mine_eval_cases()
    assert len(cases) >= 3
    categories = {c.category for c in cases}
    assert "bank_surplus" in categories
    assert "risk_gate" in categories


def test_eval_harness_runs_cleanly(tmp_path):
    dataset_file = tmp_path / "dataset.jsonl"
    miner = TraceMiner(trace_dir=tmp_path)
    miner.save_eval_dataset(dataset_file)

    harness = EvalHarness(dataset_path=dataset_file)
    report = harness.run_evals()

    assert report.total_evals >= 3
    assert report.pass_rate_pct == 100.0
    assert report.failed_count == 0
