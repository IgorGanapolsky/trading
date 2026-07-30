import pytest
from unittest.mock import patch, MagicMock
from src.observability.inception_labs_adapter import InceptionLabsMercuryAdapter, InceptionResponse


def test_inception_labs_adapter_missing_key(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SOME_KEY=123", encoding="utf-8")

    adapter = InceptionLabsMercuryAdapter(env_path=env_file)
    res = adapter.completion("Hello")

    assert res.success is False
    assert res.status_code == 401


@patch("requests.post")
def test_inception_labs_adapter_successful_completion(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "Mercury 2 response content"}}],
        "usage": {"total_tokens": 150},
    }
    mock_post.return_value = mock_resp

    adapter = InceptionLabsMercuryAdapter(api_key="test_mercury_key")
    res = adapter.completion("Test prompt")

    assert res.success is True
    assert res.status_code == 200
    assert res.content == "Mercury 2 response content"
    assert res.tokens_used == 150
