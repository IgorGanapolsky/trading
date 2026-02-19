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


def test_process_payload_writes_state_and_runs_pipeline(tmp_path: Path) -> None:
    project = tmp_path / "project"
    scripts_feedback = project / ".claude" / "scripts" / "feedback"
    memory_feedback = project / ".claude" / "memory" / "feedback"
    memalign_script = (
        project
        / "plugins"
        / "automation-plugin"
        / "skills"
        / "dynamic-agent-spawner"
        / "scripts"
    )
    scripts_feedback.mkdir(parents=True)
    memory_feedback.mkdir(parents=True)
    memalign_script.mkdir(parents=True)

    for rel in (
        scripts_feedback / "semantic-memory-v2.py",
        scripts_feedback / "train_from_feedback.py",
        scripts_feedback / "cortex_sync.py",
        memalign_script / "rlhf-integration.ts",
    ):
        rel.write_text("# placeholder\n", encoding="utf-8")

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
    assert any("semantic-memory-v2.py" in " ".join(cmd) for cmd in commands)
    assert any("train_from_feedback.py" in " ".join(cmd) for cmd in commands)
    assert any("cortex_sync.py" in " ".join(cmd) for cmd in commands)
    assert any("rlhf-integration.ts" in " ".join(cmd) for cmd in commands)

    state_file = memory_feedback / "codex_notify_state.json"
    assert state_file.exists()
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["last_signal"] == "thumbs_up"


def test_process_payload_is_idempotent_per_event_key(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / ".claude" / "scripts" / "feedback").mkdir(parents=True)
    (project / ".claude" / "memory" / "feedback").mkdir(parents=True)

    called = {"count": 0}

    def fake_runner(command: list[str], **_: object) -> int:
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

    signal = detect_feedback_signal("thumbs down")
    assert signal is not None
    assert second["event_key"] == build_event_key(payload, "thumbs down", signal)

