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
        project / "plugins" / "automation-plugin" / "skills" / "dynamic-agent-spawner" / "scripts"
    )
    scripts_feedback.mkdir(parents=True)
    memory_feedback.mkdir(parents=True)
    memalign_script.mkdir(parents=True)
    (project / ".claude" / "memory" / "feedback").mkdir(parents=True, exist_ok=True)

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
    assert any("rlhf-integration.ts" in " ".join(cmd) for cmd in commands)

    state_file = memory_feedback / "codex_notify_state.json"
    assert state_file.exists()
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["last_signal"] == "thumbs_up"
    assert state["last_pipeline_status"]["cortex_queue"] is True
    assert state["last_pipeline_status"]["distributed_bandit"] is True
    assert state["last_pipeline_status"]["context_index"] is True
    assert state["last_thompson_report"]["feedback_type"] == "positive"
    assert state["last_thompson_report"]["event_key"] == result["event_key"]
    assert state["last_distributed_outcome"]["applied"] is True

    pending = memory_feedback / "pending_cortex_sync.jsonl"
    assert pending.exists()
    assert pending.read_text(encoding="utf-8").strip()

    thompson_log = memory_feedback / "thompson_feedback_log.jsonl"
    assert thompson_log.exists()
    row = json.loads(thompson_log.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert row["event_key"] == result["event_key"]
    assert row["bandit"]["before"]["alpha"] >= 1.0
    assert row["bandit"]["after"]["beta"] >= 1.0

    context_index = project / "data" / "context_engine" / "context_index.json"
    assert context_index.exists()


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
    assert first["pipeline_status"]["distributed_bandit"] is True

    signal = detect_feedback_signal("thumbs down")
    assert signal is not None
    assert second["event_key"] == build_event_key(payload, "thumbs down", signal)

    thompson_log = project / ".claude" / "memory" / "feedback" / "thompson_feedback_log.jsonl"
    assert thompson_log.exists()
    assert (
        len([line for line in thompson_log.read_text(encoding="utf-8").splitlines() if line]) == 1
    )


def test_thompson_report_reflects_model_delta(tmp_path: Path) -> None:
    project = tmp_path / "project"
    scripts_feedback = project / ".claude" / "scripts" / "feedback"
    memory_feedback = project / ".claude" / "memory" / "feedback"
    model_file = project / "models" / "ml" / "feedback_model.json"
    scripts_feedback.mkdir(parents=True)
    memory_feedback.mkdir(parents=True)
    model_file.parent.mkdir(parents=True)

    for rel in (
        scripts_feedback / "semantic-memory-v2.py",
        scripts_feedback / "train_from_feedback.py",
    ):
        rel.write_text("# placeholder\n", encoding="utf-8")

    model_file.write_text(
        json.dumps({"alpha": 10.0, "beta": 4.0, "feature_weights": {}, "per_category": {}}),
        encoding="utf-8",
    )

    def fake_runner(command: list[str], **_: object) -> int:
        _ = command
        return 0

    payload = {
        "cwd": str(project),
        "session_id": "s2",
        "turn_id": "t-positive",
        "input-messages": ["thumbs up, that worked"],
        "last-assistant-message": "patched publishing pipeline",
    }
    result = process_payload(payload, runner=fake_runner)

    report = result["thompson_report"]
    assert report["bandit"]["before"]["alpha"] == 10.0
    assert report["bandit"]["after"]["alpha"] == 11.0
    assert report["bandit"]["delta_alpha"] == 1.0
    assert report["feedback_type"] == "positive"
    assert result["distributed_outcome"]["applied"] is True
