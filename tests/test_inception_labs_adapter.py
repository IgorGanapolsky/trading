import json
from unittest.mock import MagicMock, patch

from src.observability.inception_labs_adapter import (
    InceptionLabsMercuryAdapter,
    resolve_inception_api_key,
)


def test_inception_labs_adapter_missing_key(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SOME_KEY=123", encoding="utf-8")
    vault = tmp_path / "nope.json"

    adapter = InceptionLabsMercuryAdapter(env_path=env_file, vault_path=vault)
    res = adapter.completion("Hello")

    assert res.success is False
    assert res.status_code == 401
    assert res.error == "missing_api_key"


def test_resolve_key_from_vault(tmp_path):
    vault = tmp_path / "inception.json"
    vault.write_text(
        json.dumps({"INCEPTION_API_KEY": "sk_test_vault_key_1234567890"}),
        encoding="utf-8",
    )
    key = resolve_inception_api_key(vault_path=vault, env_path=tmp_path / "missing.env")
    assert key == "sk_test_vault_key_1234567890"


@patch("requests.post")
def test_inception_labs_adapter_successful_completion(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "Mercury 2 response content"}}],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
        },
        "model": "inception/mercury-2-prod-h100",
    }
    mock_post.return_value = mock_resp

    adapter = InceptionLabsMercuryAdapter(api_key="test_mercury_key")
    res = adapter.completion("Test prompt")

    assert res.success is True
    assert res.status_code == 200
    assert res.content == "Mercury 2 response content"
    assert res.tokens_used == 30
    assert res.prompt_tokens == 10
    assert res.completion_tokens == 20
    assert res.latency_ms >= 0
    assert res.estimated_cost_usd > 0


@patch("requests.post")
def test_run_roi_suite_aggregates(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "ok"}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
        "model": "mercury-2",
    }
    mock_post.return_value = mock_resp

    adapter = InceptionLabsMercuryAdapter(api_key="k")
    report = adapter.run_roi_suite(
        tasks=[
            {"name": "a", "prompt": "hi", "max_tokens": "16"},
            {"name": "b", "prompt": "yo", "max_tokens": "16"},
        ]
    )
    assert report.n_calls == 2
    assert report.successes == 2
    assert report.failures == 0
    assert report.total_tokens == 20
    assert report.free_tier_savings_usd > 0
    d = report.to_dict()
    assert d["avg_latency_ms"] is not None
    assert d["success_rate"] == 1.0
