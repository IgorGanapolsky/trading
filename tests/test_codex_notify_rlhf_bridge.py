from __future__ import annotations

import json
from pathlib import Path

from src.learning.codex_feedback_bridge import (
    build_event_key,
    detect_feedback_signal,
    extract_last_assistant_message,
    extract_latest_user_message,
    parse_notify_payload,
    process_payload,
)


def test_parse_notify_payload_reads_json_from_last_argument() -> None:
    payload = {"input-messages": ["thumbs up"], "turn-id": "t1"}
    argv = ["--foo", "bar", json.dumps(payload)]
    assert parse_notify_payload(argv) == payload


def test_extract_messages_from_payload() -> None:
    payload = {
        "input-messages": ["first", {"text": "thumbs down"}],
        "last-assistant-message": {"text": "status report"},
    }
    assert extract_latest_user_message(payload) == "thumbs down"
    assert extract_last_assistant_message(payload) == "status report"


def test_detect_feedback_signal_explicit_and_implicit() -> None:
    assert detect_feedback_signal("thumbs down please").signal == "thumbs_down"
    assert detect_feedback_signal("thumbs up").signal == "thumbs_up"
    assert detect_feedback_signal("revert this").signal == "undo_revert"
    assert detect_feedback_signal("looks good ship it").signal == "approval"
    assert detect_feedback_signal("neutral request") is None


def test_process_payload_records_gateway_commands_and_rlhf_state(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / ".claude").mkdir(parents=True)

    commands: list[list[str]] = []

    def fake_runner(command: list[str], **_: object) -> int:
        commands.append(command)
        return 0

    payload = {
        "cwd": str(project),
        "session_id": "s1",
        "turn_id": "t1",
        "input-messages": ["thumbs up"],
        "last-assistant-message": "done",
    }
    result = process_payload(payload, runner=fake_runner)

    assert result["status"] == "processed"
    assert any("mcp-memory-gateway@0.7.1" in " ".join(cmd) for cmd in commands)
    assert any(" capture " in f" {' '.join(cmd)} " for cmd in commands)
    assert any(" rules " in f" {' '.join(cmd)} " for cmd in commands)

    state_file = project / ".rlhf" / "codex_notify_state.json"
    assert state_file.exists()
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["last_signal"] == "thumbs_up"
    assert state["last_pipeline_status"]["gateway_capture"] is True
    assert state["last_pipeline_status"]["gateway_rules"] is True
    assert state["last_pipeline_status"]["fallback_log"] is False

    event_log = project / ".rlhf" / "codex_notify_events.jsonl"
    assert event_log.exists()
    row = json.loads(event_log.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert row["event_key"] == result["event_key"]
    assert row["pipeline_status"]["gateway_capture"] is True


def test_process_payload_falls_back_to_rlhf_log_on_gateway_failure(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / ".claude").mkdir(parents=True)

    def failing_runner(command: list[str], **_: object) -> int:
        _ = command
        return 1

    payload = {
        "cwd": str(project),
        "session_id": "s1",
        "turn_id": "t-negative",
        "input-messages": ["thumbs down"],
        "last-assistant-message": "bad patch",
    }
    result = process_payload(payload, runner=failing_runner)

    assert result["status"] == "processed"
    assert result["pipeline_status"]["gateway_capture"] is False
    assert result["pipeline_status"]["fallback_log"] is True

    feedback_log = project / ".rlhf" / "feedback-log.jsonl"
    assert feedback_log.exists()
    row = json.loads(feedback_log.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert row["signal"] == "down"
    assert row["source"] in {"user", "auto"}


def test_process_payload_is_idempotent_per_event_key(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / ".claude").mkdir(parents=True)

    called = {"count": 0}

    def fake_runner(command: list[str], **_: object) -> int:
        _ = command
        called["count"] += 1
        return 0

    payload = {
        "cwd": str(project),
        "session_id": "s1",
        "turn_id": "same-turn",
        "input-messages": ["thumbs down"],
    }

    first = process_payload(payload, runner=fake_runner)
    second = process_payload(payload, runner=fake_runner)

    assert first["status"] == "processed"
    assert second["status"] == "ignored"
    assert second["reason"] == "duplicate"
    assert called["count"] == 2

    signal = detect_feedback_signal("thumbs down")
    assert signal is not None
    assert second["event_key"] == build_event_key(payload, "thumbs down", signal)
