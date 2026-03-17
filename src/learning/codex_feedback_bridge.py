"""Codex notify-hook bridge into MCP Memory Gateway.

This bridge keeps Codex feedback on the same canonical local path used by
the hook pipeline: `.rlhf/feedback-log.jsonl` plus generated prevention rules.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from src.learning.memory_gateway_feedback import (
    append_feedback_fallback,
    build_feedback_context,
    command_return_code,
    detect_feedback_signal,
    gateway_capture_command,
    gateway_rules_command,
    normalize_text,
    run_command,
    safe_now_iso,
)


@dataclass(frozen=True)
class BridgePaths:
    project_root: Path
    rlhf_dir: Path
    state_file: Path
    event_log: Path
    prevention_rules: Path


def _normalize_payload_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("text", "message", "prompt", "content", "input"):
            nested = _normalize_payload_text(value.get(key))
            if nested:
                return nested
        return ""
    if isinstance(value, list):
        parts = [_normalize_payload_text(item) for item in value]
        return " ".join(part for part in parts if part).strip()
    return str(value).strip()


def parse_notify_payload(argv: list[str]) -> dict[str, Any] | None:
    for raw in reversed(argv):
        candidate = raw.strip()
        if not candidate or not candidate.startswith("{"):
            continue
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def extract_latest_user_message(payload: dict[str, Any]) -> str:
    for key in ("input-messages", "input_messages", "inputMessages"):
        items = payload.get(key)
        if isinstance(items, list):
            messages = [_normalize_payload_text(item) for item in items]
            messages = [msg for msg in messages if msg]
            if messages:
                return messages[-1]

    for key in ("prompt", "user_message", "input"):
        message = _normalize_payload_text(payload.get(key))
        if message:
            return message
    return ""


def extract_last_assistant_message(payload: dict[str, Any]) -> str:
    for key in (
        "last-assistant-message",
        "last_assistant_message",
        "lastAssistantMessage",
        "assistant_response",
        "assistantResponse",
    ):
        message = _normalize_payload_text(payload.get(key))
        if message:
            return message
    return ""


def _find_project_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / ".claude").exists():
            return candidate
    return start


def resolve_paths(payload: dict[str, Any], cwd: Path | None = None) -> BridgePaths:
    payload_cwd = _normalize_payload_text(payload.get("cwd")) if payload else ""
    base = (
        Path(payload_cwd).expanduser().resolve() if payload_cwd else (cwd or Path.cwd()).resolve()
    )
    project_root = _find_project_root(base)
    rlhf_dir = project_root / ".rlhf"
    return BridgePaths(
        project_root=project_root,
        rlhf_dir=rlhf_dir,
        state_file=rlhf_dir / "codex_notify_state.json",
        event_log=rlhf_dir / "codex_notify_events.jsonl",
        prevention_rules=rlhf_dir / "prevention-rules.md",
    )


def _read_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"recent_event_keys": []}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"recent_event_keys": []}
    if not isinstance(raw, dict):
        return {"recent_event_keys": []}
    keys = raw.get("recent_event_keys", [])
    raw["recent_event_keys"] = keys if isinstance(keys, list) else []
    return raw


def _write_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True) + "\n")


def build_event_key(payload: dict[str, Any], user_message: str, signal: Any) -> str:
    session_id = _normalize_payload_text(
        payload.get("session_id") or payload.get("session-id") or payload.get("sessionId")
    )
    turn_id = _normalize_payload_text(
        payload.get("turn_id") or payload.get("turn-id") or payload.get("turnId")
    )
    timestamp = _normalize_payload_text(payload.get("timestamp") or payload.get("ts"))

    if session_id and turn_id:
        return f"{session_id}:{turn_id}:{signal.signal}"

    seed = f"{session_id}|{turn_id}|{timestamp}|{signal.signal}|{user_message}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]


Runner = Callable[..., Any]


def process_payload(
    payload: dict[str, Any],
    *,
    cwd: Path | None = None,
    runner: Runner = run_command,
) -> dict[str, Any]:
    paths = resolve_paths(payload, cwd=cwd)
    if not (paths.project_root / ".claude").exists():
        return {"status": "ignored", "reason": "no_claude_dir"}

    user_message = normalize_text(extract_latest_user_message(payload), limit=1000)
    signal = detect_feedback_signal(user_message)
    if signal is None:
        return {"status": "ignored", "reason": "no_feedback_signal"}

    assistant_message = normalize_text(extract_last_assistant_message(payload), limit=500)
    context, detail, improvement = build_feedback_context(signal, user_message, assistant_message)
    event_key = build_event_key(payload, user_message, signal)

    state = _read_state(paths.state_file)
    recent_keys = state.get("recent_event_keys", [])
    if event_key in recent_keys:
        return {"status": "ignored", "reason": "duplicate", "event_key": event_key}

    capture_result = runner(
        gateway_capture_command(signal, context, detail, improvement),
        cwd=paths.project_root,
    )
    capture_ok = command_return_code(capture_result) in {0, 2}

    rules_ok = False
    fallback_log = None
    if capture_ok:
        rules_result = runner(
            gateway_rules_command(paths.prevention_rules),
            cwd=paths.project_root,
        )
        rules_ok = command_return_code(rules_result) == 0
    else:
        fallback_log = append_feedback_fallback(
            project_root=paths.project_root,
            signal=signal,
            context=context,
            user_message=user_message,
            assistant_response=assistant_message,
        )

    pipeline_status = {
        "gateway_capture": capture_ok,
        "gateway_rules": rules_ok,
        "fallback_log": fallback_log is not None,
    }

    event_record = {
        "event_key": event_key,
        "timestamp": safe_now_iso(),
        "signal": signal.signal,
        "feedback": signal.feedback,
        "context": context,
        "assistant_message": assistant_message,
        "pipeline_status": pipeline_status,
        "fallback_log": str(fallback_log) if fallback_log else None,
    }
    _append_jsonl(paths.event_log, event_record)

    recent_keys.append(event_key)
    state.update(
        {
            "last_event_key": event_key,
            "last_signal": signal.signal,
            "last_feedback": signal.feedback,
            "last_updated": safe_now_iso(),
            "recent_event_keys": recent_keys[-500:],
            "last_pipeline_status": pipeline_status,
            "last_event_record": event_record,
        }
    )
    _write_state(paths.state_file, state)

    return {
        "status": "processed",
        "event_key": event_key,
        "signal": signal.signal,
        "feedback": signal.feedback,
        "pipeline_status": pipeline_status,
        "event_record": event_record,
    }


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    payload = parse_notify_payload(args)
    if payload is None:
        return 0
    try:
        process_payload(payload)
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
