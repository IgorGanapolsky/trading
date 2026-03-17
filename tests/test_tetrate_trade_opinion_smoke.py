from __future__ import annotations

import json
from pathlib import Path

from scripts.tetrate_trade_opinion_smoke import build_artifact_fallback_result


def test_artifact_fallback_marks_router_check_as_actionable(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts" / "tars"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "smoke_response.json").write_text(
        json.dumps(
            {
                "id": "req_123",
                "model": "gpt-4o-mini",
                "choices": [
                    {
                        "message": {
                            "content": '```json\n{"status":"success","router_check":true}\n```'
                        }
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (artifact_dir / "smoke_metrics.txt").write_text(
        "gateway_base_url_host=api.router.tetrate.ai\n",
        encoding="utf-8",
    )

    result = build_artifact_fallback_result(tmp_path)

    assert result["source"] == "artifact_fallback"
    assert result["actionable"] is True
    assert result["decision"] == "hold"
    assert result["router_check"] is True
    assert result["request_id"] == "req_123"
    assert result["gateway_base_url_host"] == "api.router.tetrate.ai"
