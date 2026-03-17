from __future__ import annotations

import json
from pathlib import Path

from scripts.capture_hook_feedback import process_user_message


def test_process_user_message_ignores_non_feedback(tmp_path: Path) -> None:
    result = process_user_message("show me the latest account balance", project_root=tmp_path)
    assert result["status"] == "ignored"


def test_process_user_message_uses_gateway_commands(tmp_path: Path) -> None:
    commands: list[list[str]] = []

    def fake_runner(command: list[str], **_: object) -> int:
        commands.append(command)
        return 0

    result = process_user_message(
        "thumbs up",
        project_root=tmp_path,
        runner=fake_runner,
    )

    assert result["status"] == "processed"
    assert result["accepted"] is True
    assert result["rules_refreshed"] is True
    assert any("mcp-memory-gateway@0.7.1" in " ".join(cmd) for cmd in commands)
    assert any(" capture " in f" {' '.join(cmd)} " for cmd in commands)
    assert any(" rules " in f" {' '.join(cmd)} " for cmd in commands)


def test_process_user_message_falls_back_when_gateway_fails(tmp_path: Path) -> None:
    def failing_runner(command: list[str], **_: object) -> int:
        _ = command
        return 1

    result = process_user_message(
        "thumbs down",
        project_root=tmp_path,
        runner=failing_runner,
    )

    assert result["status"] == "processed"
    assert result["accepted"] is False
    assert result["fallback_log"] is not None

    feedback_log = tmp_path / ".rlhf" / "feedback-log.jsonl"
    assert feedback_log.exists()
    row = json.loads(feedback_log.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert row["signal"] == "down"
