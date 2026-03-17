"""Shared MCP Memory Gateway helpers for local agent feedback."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

GATEWAY_VERSION = "0.7.1"
TRANSCRIPT_ROOT = Path.home() / ".claude" / "projects"

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
    r"that's wrong|try again|start over|thumbs down",
    re.IGNORECASE,
)
IMPLICIT_POSITIVE_RE = re.compile(
    r"ship it|merge it|lgtm|looks good|that works|worked|proceed|thumbs up",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FeedbackSignal:
    feedback: str
    signal: str
    source: str
    context_label: str
    tags: tuple[str, ...]


def safe_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_text(value: str, *, limit: int = 2000) -> str:
    compact = re.sub(r"\s+", " ", value).strip()
    return compact[:limit]


def detect_feedback_signal(message: str) -> FeedbackSignal | None:
    if not message:
        return None
    if EXPLICIT_NEGATIVE_RE.search(message):
        return FeedbackSignal(
            feedback="down",
            signal="thumbs_down",
            source="user",
            context_label="User thumbs down on assistant response",
            tags=("explicit", "thumbs-down", "memory-gateway"),
        )
    if EXPLICIT_POSITIVE_RE.search(message):
        return FeedbackSignal(
            feedback="up",
            signal="thumbs_up",
            source="user",
            context_label="User thumbs up on assistant response",
            tags=("explicit", "thumbs-up", "memory-gateway"),
        )
    if IMPLICIT_NEGATIVE_RE.search(message):
        return FeedbackSignal(
            feedback="down",
            signal="undo_revert",
            source="auto",
            context_label="Implicit negative on assistant response",
            tags=("implicit", "undo-revert", "memory-gateway"),
        )
    if IMPLICIT_POSITIVE_RE.search(message):
        return FeedbackSignal(
            feedback="up",
            signal="approval",
            source="auto",
            context_label="Implicit positive on assistant response",
            tags=("implicit", "approval", "memory-gateway"),
        )
    return None


def extract_last_assistant_response(transcript_root: Path = TRANSCRIPT_ROOT) -> str:
    if not transcript_root.exists():
        return ""

    latest_transcript: Path | None = None
    latest_mtime = -1.0
    for path in transcript_root.rglob("*.jsonl"):
        try:
            stat = path.stat()
        except OSError:
            continue
        if stat.st_mtime > latest_mtime:
            latest_transcript = path
            latest_mtime = stat.st_mtime

    if latest_transcript is None:
        return ""

    try:
        lines = latest_transcript.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""

    for raw in reversed(lines[-50:]):
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if obj.get("type") != "assistant":
            continue
        message = obj.get("message", {})
        content = message.get("content", [])
        if not isinstance(content, list):
            continue
        text_parts = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        response = normalize_text(" ".join(text_parts), limit=500)
        if response:
            return response
    return ""


def build_feedback_context(
    signal: FeedbackSignal,
    user_message: str,
    assistant_response: str,
) -> tuple[str, str, str]:
    if assistant_response:
        context = f"{signal.context_label}: {assistant_response}"
    else:
        context = f"{signal.context_label}: {normalize_text(user_message, limit=500)}"

    if signal.feedback == "down":
        what_went_wrong = normalize_text(
            assistant_response or user_message or "Hook captured a negative feedback signal.",
            limit=500,
        )
        what_to_change = normalize_text(
            f"Review the assistant response before taking the next similar action. "
            f"Latest user message: {user_message}",
            limit=500,
        )
        return context, what_went_wrong, what_to_change

    what_worked = normalize_text(
        assistant_response or user_message or "Hook captured a positive feedback signal.",
        limit=500,
    )
    return context, what_worked, ""


def gateway_capture_command(
    signal: FeedbackSignal,
    context: str,
    detail: str,
    improvement: str,
) -> list[str]:
    command = [
        "npx",
        "-y",
        f"mcp-memory-gateway@{GATEWAY_VERSION}",
        "capture",
        f"--feedback={signal.feedback}",
        f"--context={context}",
        f"--tags={','.join(signal.tags)}",
    ]
    if signal.feedback == "down":
        command.append(f"--what-went-wrong={detail}")
        command.append(f"--what-to-change={improvement}")
    else:
        command.append(f"--what-worked={detail}")
    return command


def gateway_rules_command(output_path: Path) -> list[str]:
    return [
        "npx",
        "-y",
        f"mcp-memory-gateway@{GATEWAY_VERSION}",
        "rules",
        f"--output={output_path}",
        "--min=2",
    ]


def append_feedback_fallback(
    *,
    project_root: Path,
    signal: FeedbackSignal,
    context: str,
    user_message: str,
    assistant_response: str,
) -> Path:
    rlhf_dir = project_root / ".rlhf"
    rlhf_dir.mkdir(parents=True, exist_ok=True)
    log_path = rlhf_dir / "feedback-log.jsonl"
    entry = {
        "id": f"fb_{hashlib.md5((context + safe_now_iso()).encode('utf-8')).hexdigest()[:10]}",
        "timestamp": safe_now_iso(),
        "signal": signal.feedback,
        "context": context,
        "source": signal.source,
        "tags": list(signal.tags),
        "user_message": normalize_text(user_message, limit=500),
        "assistant_response": normalize_text(assistant_response, limit=500),
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True) + "\n")
    return log_path


def run_command(
    command: Sequence[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout: int = 90,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def command_return_code(result: Any) -> int:
    if isinstance(result, int):
        return result
    return int(getattr(result, "returncode", 1))
