"""Codex notify-hook bridge into the repo's hybrid RLHF pipeline.

This bridge is designed for Codex CLI `notify` payloads. It detects explicit
and implicit feedback signals from user messages and fans them out to the
existing local RLHF stack:

1. feedback-log.jsonl (+ LanceDB via semantic-memory-v2.py)
2. Thompson model incremental training
3. ShieldCortex queue (cortex_sync.py --queue)
4. MemAlign + Cortex immediate sync (rlhf-integration.ts record)

The bridge is idempotent per turn/event key to avoid duplicate writes.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


EXPLICIT_NEGATIVE_RE = re.compile(
    r"thumbs\s*down|👎|bad response|wrong answer|incorrect|not what i asked",
    re.IGNORECASE,
)
EXPLICIT_POSITIVE_RE = re.compile(
    r"thumbs\s*up|👍|great|good job|well done|perfect|excellent|approved",
    re.IGNORECASE,
)
IMPLICIT_NEGATIVE_RE = re.compile(
    r"undo|revert|rollback|go back|restore|that broke|that failed|"
    r"that's wrong|try again|start over",
    re.IGNORECASE,
)
IMPLICIT_POSITIVE_RE = re.compile(
    r"ship it|merge it|lgtm|looks good|that works|worked|proceed",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FeedbackSignal:
    feedback_type: str
    reward: float
    source: str
    signal: str
    tags: list[str]
    intensity: int
    label: str


@dataclass(frozen=True)
class BridgePaths:
    project_root: Path
    feedback_dir: Path
    state_file: Path
    pending_cortex_queue: Path
    semantic_memory_py: Path
    train_script_py: Path
    cortex_sync_py: Path
    venv_python: Path
    memalign_record_ts: Path


def _safe_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("text", "message", "prompt", "content", "input"):
            nested = _normalize_text(value.get(key))
            if nested:
                return nested
        return ""
    if isinstance(value, list):
        parts = [_normalize_text(item) for item in value]
        return " ".join(part for part in parts if part).strip()
    return str(value).strip()


def parse_notify_payload(argv: list[str]) -> dict[str, Any] | None:
    """Parse notify payload JSON from argv, if present."""
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
            messages = [_normalize_text(item) for item in items]
            messages = [msg for msg in messages if msg]
            if messages:
                return messages[-1]

    for key in ("prompt", "user_message", "input"):
        msg = _normalize_text(payload.get(key))
        if msg:
            return msg

    return ""


def extract_last_assistant_message(payload: dict[str, Any]) -> str:
    for key in (
        "last-assistant-message",
        "last_assistant_message",
        "lastAssistantMessage",
        "assistant_response",
        "assistantResponse",
    ):
        msg = _normalize_text(payload.get(key))
        if msg:
            return msg
    return ""


def detect_feedback_signal(message: str) -> FeedbackSignal | None:
    if not message:
        return None

    if EXPLICIT_NEGATIVE_RE.search(message):
        return FeedbackSignal(
            feedback_type="negative",
            reward=-1.0,
            source="user",
            signal="thumbs_down",
            tags=["explicit", "thumbs-down"],
            intensity=4,
            label="explicit_negative",
        )
    if EXPLICIT_POSITIVE_RE.search(message):
        return FeedbackSignal(
            feedback_type="positive",
            reward=1.0,
            source="user",
            signal="thumbs_up",
            tags=["explicit", "thumbs-up"],
            intensity=4,
            label="explicit_positive",
        )
    if IMPLICIT_NEGATIVE_RE.search(message):
        return FeedbackSignal(
            feedback_type="negative",
            reward=-0.5,
            source="auto",
            signal="undo_revert",
            tags=["implicit", "undo-revert"],
            intensity=2,
            label="implicit_negative",
        )
    if IMPLICIT_POSITIVE_RE.search(message):
        return FeedbackSignal(
            feedback_type="positive",
            reward=0.5,
            source="auto",
            signal="approval",
            tags=["implicit", "approval"],
            intensity=2,
            label="implicit_positive",
        )
    return None


def _sanitize_one_line(text: str, limit: int = 2000) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    return compact[:limit]


def build_feedback_context(
    signal: FeedbackSignal,
    user_message: str,
    assistant_message: str,
) -> str:
    if assistant_message:
        if signal.label == "explicit_positive":
            return f"User thumbs up on assistant response: {assistant_message}"
        if signal.label == "explicit_negative":
            return f"User thumbs down on assistant response: {assistant_message}"
        if signal.label == "implicit_positive":
            return f"IMPLICIT POSITIVE (approval) on assistant response: {assistant_message}"
        return f"IMPLICIT NEGATIVE (undo/revert) on assistant response: {assistant_message}"

    if signal.label.startswith("explicit"):
        return f"User feedback: {user_message}"
    if signal.label == "implicit_positive":
        return f"IMPLICIT POSITIVE: User approved/continued. User message: {user_message}"
    return f"IMPLICIT NEGATIVE: User signaled undo/revert. User message: {user_message}"


def _find_project_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / ".claude").exists():
            return candidate
    return start


def resolve_paths(payload: dict[str, Any], cwd: Path | None = None) -> BridgePaths:
    payload_cwd = _normalize_text(payload.get("cwd")) if payload else ""
    if payload_cwd:
        base = Path(payload_cwd).expanduser().resolve()
    else:
        base = (cwd or Path.cwd()).resolve()

    project_root = _find_project_root(base)
    feedback_dir = project_root / ".claude" / "memory" / "feedback"
    scripts_dir = project_root / ".claude" / "scripts" / "feedback"
    return BridgePaths(
        project_root=project_root,
        feedback_dir=feedback_dir,
        state_file=feedback_dir / "codex_notify_state.json",
        pending_cortex_queue=feedback_dir / "pending_cortex_sync.jsonl",
        semantic_memory_py=scripts_dir / "semantic-memory-v2.py",
        train_script_py=scripts_dir / "train_from_feedback.py",
        cortex_sync_py=scripts_dir / "cortex_sync.py",
        venv_python=scripts_dir / "venv" / "bin" / "python3",
        memalign_record_ts=(
            project_root
            / "plugins"
            / "automation-plugin"
            / "skills"
            / "dynamic-agent-spawner"
            / "scripts"
            / "rlhf-integration.ts"
        ),
    )


def _read_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"recent_event_keys": []}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            keys = raw.get("recent_event_keys", [])
            if not isinstance(keys, list):
                keys = []
            raw["recent_event_keys"] = keys
            return raw
    except (OSError, json.JSONDecodeError):
        pass
    return {"recent_event_keys": []}


def _write_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def build_event_key(
    payload: dict[str, Any],
    user_message: str,
    signal: FeedbackSignal,
) -> str:
    session_id = _normalize_text(
        payload.get("session_id")
        or payload.get("session-id")
        or payload.get("sessionId")
    )
    turn_id = _normalize_text(
        payload.get("turn_id") or payload.get("turn-id") or payload.get("turnId")
    )
    timestamp = _normalize_text(payload.get("timestamp") or payload.get("ts"))

    if session_id and turn_id:
        return f"{session_id}:{turn_id}:{signal.signal}"

    seed = f"{session_id}|{turn_id}|{timestamp}|{signal.signal}|{user_message}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]


def _python_bin(paths: BridgePaths) -> str:
    candidates: list[str] = []
    if paths.venv_python.exists():
        candidates.append(str(paths.venv_python))
    if sys.executable:
        candidates.append(sys.executable)
    candidates.append("python3")

    for candidate in candidates:
        try:
            probe = subprocess.run(
                [candidate, "--version"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            if probe.returncode == 0:
                return candidate
        except Exception:
            continue
    return "python3"


def _run_subprocess(
    command: list[str],
    *,
    stdin_text: str | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 30,
) -> int:
    completed = subprocess.run(
        command,
        input=stdin_text,
        text=True,
        capture_output=True,
        timeout=timeout,
        env=env,
        check=False,
    )
    return int(completed.returncode)


Runner = Callable[..., int]


def _append_feedback_jsonl_fallback(
    paths: BridgePaths,
    signal: FeedbackSignal,
    context: str,
    user_message: str,
    assistant_message: str,
) -> None:
    feedback_log = paths.feedback_dir / "feedback-log.jsonl"
    paths.feedback_dir.mkdir(parents=True, exist_ok=True)
    entry = {
        "id": f"fb_{hashlib.md5((_safe_now_iso() + context[:50]).encode('utf-8')).hexdigest()[:8]}",
        "timestamp": _safe_now_iso(),
        "feedback": signal.feedback_type,
        "context": context,
        "tags": signal.tags,
        "reward": signal.reward,
        "source": signal.source,
        "signal": signal.signal,
        "user_message": _sanitize_one_line(user_message),
        "assistant_response": _sanitize_one_line(assistant_message),
    }
    with feedback_log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True) + "\n")


def _queue_cortex_pending(paths: BridgePaths, signal: FeedbackSignal, context: str) -> bool:
    """Queue ShieldCortex sync item without re-writing feedback-log.jsonl."""
    try:
        queue_file = paths.pending_cortex_queue
        queue_file.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "id": f"fb_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{signal.feedback_type[:3]}",
            "timestamp": _safe_now_iso(),
            "signal": signal.feedback_type,
            "intensity": signal.intensity,
            "context": context,
            "tool_name": "codex_notify_bridge",
            "files": [],
            "source": signal.source,
            "synced": False,
        }
        with queue_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=True) + "\n")
        return True
    except OSError:
        return False


def _run_feedback_pipeline(
    paths: BridgePaths,
    payload: dict[str, Any],
    signal: FeedbackSignal,
    context: str,
    user_message: str,
    assistant_message: str,
    runner: Runner,
) -> dict[str, bool]:
    py = _python_bin(paths)
    tags_csv = ",".join(signal.tags)
    result = {
        "semantic": False,
        "train": False,
        "cortex_queue": False,
        "memalign_record": False,
    }

    if paths.semantic_memory_py.exists():
        semantic_cmd = [
            py,
            str(paths.semantic_memory_py),
            "--add-feedback",
            "--feedback-type",
            signal.feedback_type,
            "--reward",
            str(signal.reward),
            "--source",
            signal.source,
            "--signal",
            signal.signal,
            "--tags",
            tags_csv,
        ]
        if signal.source == "auto":
            semantic_cmd.append("--no-reindex")
        if runner(semantic_cmd, stdin_text=context, timeout=90) == 0:
            result["semantic"] = True
        else:
            _append_feedback_jsonl_fallback(paths, signal, context, user_message, assistant_message)
    else:
        _append_feedback_jsonl_fallback(paths, signal, context, user_message, assistant_message)

    if paths.train_script_py.exists():
        train_cmd = [py, str(paths.train_script_py), "--incremental"]
        if runner(train_cmd, timeout=60) == 0:
            result["train"] = True

    result["cortex_queue"] = _queue_cortex_pending(paths, signal, context)

    if paths.memalign_record_ts.exists():
        task_id = (
            _normalize_text(payload.get("turn_id") or payload.get("turn-id"))
            or _normalize_text(payload.get("session_id"))
            or f"codex-{hashlib.md5(context.encode('utf-8')).hexdigest()[:8]}"
        )
        decision = _sanitize_one_line(assistant_message or "codex_notify_feedback", limit=500)
        thumbs_signal = "thumbs_up" if signal.feedback_type == "positive" else "thumbs_down"
        env = dict(os.environ)
        env["TS_NODE_TRANSPILE_ONLY"] = "1"
        env["TS_NODE_COMPILER_OPTIONS"] = (
            '{"module":"NodeNext","moduleResolution":"NodeNext","allowImportingTsExtensions":true}'
        )
        memalign_cmd = [
            "npx",
            "ts-node",
            "--transpile-only",
            str(paths.memalign_record_ts),
            "record",
            task_id,
            decision,
            thumbs_signal,
            context,
        ]
        if runner(memalign_cmd, env=env, timeout=90) == 0:
            result["memalign_record"] = True

    return result


def process_payload(
    payload: dict[str, Any],
    *,
    cwd: Path | None = None,
    runner: Runner = _run_subprocess,
) -> dict[str, Any]:
    paths = resolve_paths(payload, cwd=cwd)
    if not (paths.project_root / ".claude").exists():
        return {"status": "ignored", "reason": "no_claude_dir"}

    user_message = extract_latest_user_message(payload)
    signal = detect_feedback_signal(user_message)
    if signal is None:
        return {"status": "ignored", "reason": "no_feedback_signal"}

    assistant_message = extract_last_assistant_message(payload)
    context = _sanitize_one_line(build_feedback_context(signal, user_message, assistant_message))
    event_key = build_event_key(payload, user_message, signal)

    state = _read_state(paths.state_file)
    recent_keys = state.get("recent_event_keys", [])
    if event_key in recent_keys:
        return {"status": "ignored", "reason": "duplicate", "event_key": event_key}

    pipeline_status = _run_feedback_pipeline(
        paths,
        payload,
        signal,
        context,
        user_message,
        assistant_message,
        runner,
    )

    recent_keys.append(event_key)
    recent_keys = recent_keys[-500:]
    state.update(
        {
            "last_event_key": event_key,
            "last_signal": signal.signal,
            "last_feedback_type": signal.feedback_type,
            "last_updated": _safe_now_iso(),
            "recent_event_keys": recent_keys,
            "last_pipeline_status": pipeline_status,
        }
    )
    _write_state(paths.state_file, state)

    return {
        "status": "processed",
        "event_key": event_key,
        "signal": signal.signal,
        "feedback_type": signal.feedback_type,
        "paths": {"project_root": str(paths.project_root)},
        "pipeline_status": pipeline_status,
    }


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    payload = parse_notify_payload(args)
    if payload is None:
        return 0
    try:
        process_payload(payload)
    except Exception:
        # Never break Codex notify path.
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
