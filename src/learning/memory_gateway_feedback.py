"""Shared ThumbGate helpers for local agent feedback and repo integration."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

THUMBGATE_VERSION = "1.5.0"
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
USEFUL_LESSON_RE = re.compile(r"[A-Za-z]{4,}")


@dataclass(frozen=True)
class FeedbackSignal:
    feedback: str
    signal: str
    source: str
    context_label: str
    tags: tuple[str, ...]


@dataclass(frozen=True)
class ThumbgatePaths:
    project_root: Path
    canonical_root: Path
    feedback_dir: Path
    legacy_feedback_dir: Path
    prevention_rules: Path
    summary_path: Path
    feedback_log: Path
    memory_log: Path
    recent_lesson_path: Path


@dataclass(frozen=True)
class LessonHint:
    title: str
    snippet: str
    category: str
    tags: tuple[str, ...]
    timestamp: str
    score: int


def safe_now_iso() -> str:
    return datetime.now(UTC).isoformat()


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
            tags=("explicit", "thumbs-down", "thumbgate"),
        )
    if EXPLICIT_POSITIVE_RE.search(message):
        return FeedbackSignal(
            feedback="up",
            signal="thumbs_up",
            source="user",
            context_label="User thumbs up on assistant response",
            tags=("explicit", "thumbs-up", "thumbgate"),
        )
    if IMPLICIT_NEGATIVE_RE.search(message):
        return FeedbackSignal(
            feedback="down",
            signal="undo_revert",
            source="auto",
            context_label="Implicit negative on assistant response",
            tags=("implicit", "undo-revert", "thumbgate"),
        )
    if IMPLICIT_POSITIVE_RE.search(message):
        return FeedbackSignal(
            feedback="up",
            signal="approval",
            source="auto",
            context_label="Implicit positive on assistant response",
            tags=("implicit", "approval", "thumbgate"),
        )
    return None


def run_command(
    command: Sequence[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout: int = 90,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # nosec B603
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


def _run_git(args: Sequence[str], cwd: Path) -> str:
    result = run_command(["git", *args], cwd=cwd, timeout=15)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _find_project_root(start: Path) -> Path:
    candidate = start.resolve()
    git_root = _run_git(["rev-parse", "--show-toplevel"], candidate)
    if git_root:
        return Path(git_root).resolve()

    for path in (candidate, *candidate.parents):
        if (path / ".claude").exists() or (path / ".git").exists():
            return path
    return candidate


def parse_worktree_list(raw: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}

    for line in raw.splitlines():
        if not line.strip():
            if current:
                entries.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value

    if current:
        entries.append(current)
    return entries


def _select_canonical_root(project_root: Path) -> Path:
    raw = _run_git(["worktree", "list", "--porcelain"], project_root)
    entries = parse_worktree_list(raw)
    if not entries:
        return project_root

    for entry in entries:
        candidate = entry.get("worktree")
        if candidate and f"{os.sep}.worktrees{os.sep}" not in candidate:
            return Path(candidate).resolve()

    first = entries[0].get("worktree")
    return Path(first).resolve() if first else project_root


def resolve_thumbgate_paths(project_root: Path) -> ThumbgatePaths:
    root = _find_project_root(project_root)
    canonical_root = _select_canonical_root(root)
    canonical_thumbgate = canonical_root / ".thumbgate"
    legacy_feedback_dir = canonical_root / ".rlhf"

    if canonical_thumbgate.exists():
        feedback_dir = canonical_thumbgate
    elif legacy_feedback_dir.exists():
        feedback_dir = legacy_feedback_dir
    else:
        feedback_dir = canonical_thumbgate

    return ThumbgatePaths(
        project_root=root,
        canonical_root=canonical_root,
        feedback_dir=feedback_dir,
        legacy_feedback_dir=legacy_feedback_dir,
        prevention_rules=feedback_dir / "prevention-rules.md",
        summary_path=feedback_dir / "feedback-summary.json",
        feedback_log=feedback_dir / "feedback-log.jsonl",
        memory_log=feedback_dir / "memory-log.jsonl",
        recent_lesson_path=feedback_dir / "recent-lesson.json",
    )


def thumbgate_env(
    project_root: Path,
    *,
    include_gates: bool = False,
    extra_env: dict[str, str] | None = None,
) -> dict[str, str]:
    paths = resolve_thumbgate_paths(project_root)
    env = dict(os.environ)
    env["THUMBGATE_PROJECT_DIR"] = str(paths.project_root)
    env["CLAUDE_PROJECT_DIR"] = str(paths.project_root)
    env["THUMBGATE_FEEDBACK_DIR"] = str(paths.feedback_dir)
    env["THUMBGATE_LEGACY_FEEDBACK_DIR"] = str(paths.legacy_feedback_dir)
    if include_gates:
        env["THUMBGATE_GATES_CONFIG"] = str(
            paths.project_root / "config" / "memory-gateway" / "gates.json"
        )
    if extra_env:
        env.update(extra_env)
    return env


def thumbgate_capture_command(
    signal: FeedbackSignal,
    context: str,
    detail: str,
    improvement: str,
) -> list[str]:
    command = [
        "npx",
        "-y",
        f"thumbgate@{THUMBGATE_VERSION}",
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


def thumbgate_rules_command(output_path: Path) -> list[str]:
    return [
        "npx",
        "-y",
        f"thumbgate@{THUMBGATE_VERSION}",
        "rules",
        f"--output={output_path}",
        "--min=2",
    ]


def thumbgate_session_start_command() -> list[str]:
    return ["npx", "-y", f"thumbgate@{THUMBGATE_VERSION}", "session-start"]


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


def append_feedback_fallback(
    *,
    project_root: Path,
    signal: FeedbackSignal,
    context: str,
    user_message: str,
    assistant_response: str,
) -> Path:
    paths = resolve_thumbgate_paths(project_root)
    paths.feedback_dir.mkdir(parents=True, exist_ok=True)
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
    with paths.feedback_log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True) + "\n")
    return paths.feedback_log


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def read_feedback_counts(project_root: Path) -> dict[str, int]:
    paths = resolve_thumbgate_paths(project_root)
    summary = _load_json(paths.summary_path)
    if summary:
        return {
            "total": int(summary.get("total", 0) or 0),
            "positive": int(summary.get("positive", 0) or 0),
            "negative": int(summary.get("negative", 0) or 0),
        }

    counts = {"total": 0, "positive": 0, "negative": 0}
    if not paths.feedback_log.exists():
        return counts

    for raw in paths.feedback_log.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        counts["total"] += 1
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue
        signal = str(entry.get("signal", "")).lower()
        if signal in {"positive", "up", "thumbs_up"}:
            counts["positive"] += 1
        elif signal in {"negative", "down", "thumbs_down", "undo_revert"}:
            counts["negative"] += 1
    return counts


def _jsonl_entries(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return ()
    entries: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            entries.append(parsed)
    return entries


def _lesson_snippet(entry: dict[str, Any]) -> str:
    title = normalize_text(str(entry.get("title", "")), limit=160)
    content = normalize_text(str(entry.get("content", "")), limit=240)
    recent_lesson = normalize_text(str(entry.get("lesson", "")), limit=160)
    base = recent_lesson or content or title
    base = re.sub(r"^(SUCCESS:|MISTAKE:)\s*", "", base).strip()
    base = base.replace('{"session_id"', "").strip()
    return normalize_text(base, limit=140)


def _is_useful_lesson(entry: dict[str, Any]) -> bool:
    text = " ".join(
        [
            str(entry.get("title", "")),
            str(entry.get("content", "")),
            str(entry.get("lesson", "")),
        ]
    )
    lowered = text.lower()
    if '"session_id"' in lowered or "transcript_path" in lowered:
        return False
    return bool(USEFUL_LESSON_RE.search(text))


def _command_keywords(command: str) -> set[str]:
    lowered = command.lower()
    keywords = {token for token in re.findall(r"[a-z0-9_.-]+", lowered) if len(token) > 1}
    if "git" in keywords or "gh" in keywords:
        keywords.update({"push", "pr", "merge", "branch", "review", "ci"})
    if "push" in keywords:
        keywords.update({"review", "threads", "snapshot", "trunk"})
    if "pytest" in keywords or "ruff" in keywords:
        keywords.update({"ci", "tests", "lint"})
    if ".claude" in lowered or "agents.md" in lowered or "claude.md" in lowered:
        keywords.update({"protected-file", "scope", "task-scope", "thumbgate"})
    return keywords


def _score_lesson(entry: dict[str, Any], keywords: set[str]) -> int:
    text = " ".join(
        [
            str(entry.get("title", "")),
            str(entry.get("content", "")),
            str(entry.get("lesson", "")),
            " ".join(str(tag) for tag in entry.get("tags", []) if isinstance(tag, str)),
        ]
    ).lower()
    title = str(entry.get("title", "")).lower()
    score = 0
    for keyword in keywords:
        if keyword in title:
            score += 4
        elif keyword in text:
            score += 2

    category = str(entry.get("category", "")).lower()
    if category == "learning":
        score += 2
    elif category == "error":
        score += 1

    occurrences = entry.get("occurrences")
    if isinstance(occurrences, int) and occurrences > 1:
        score += min(occurrences, 3)

    return score


def _entry_matches_keywords(entry: dict[str, Any], keywords: set[str]) -> bool:
    text = " ".join(
        [
            str(entry.get("title", "")),
            str(entry.get("content", "")),
            str(entry.get("lesson", "")),
            " ".join(str(tag) for tag in entry.get("tags", []) if isinstance(tag, str)),
        ]
    ).lower()
    return any(keyword in text for keyword in keywords)


def select_relevant_lessons(
    project_root: Path,
    *,
    command: str = "",
    limit: int = 2,
) -> list[LessonHint]:
    paths = resolve_thumbgate_paths(project_root)
    keywords = _command_keywords(command)
    candidates: list[LessonHint] = []
    seen: set[str] = set()

    recent_lesson = _load_json(paths.recent_lesson_path)
    if recent_lesson and _is_useful_lesson(recent_lesson):
        text = " ".join(
            [
                str(recent_lesson.get("lesson", "")),
                " ".join(str(tag) for tag in recent_lesson.get("tags", [])),
            ]
        ).lower()
        score = 1 + sum(2 for keyword in keywords if keyword in text)
        snippet = _lesson_snippet(recent_lesson)
        if snippet:
            seen.add(snippet)
            candidates.append(
                LessonHint(
                    title=normalize_text(str(recent_lesson.get("lesson", "")), limit=120),
                    snippet=snippet,
                    category="lesson",
                    tags=tuple(str(tag) for tag in recent_lesson.get("tags", [])),
                    timestamp=str(recent_lesson.get("createdAt", "")),
                    score=score,
                )
            )

    entries = list(_jsonl_entries(paths.memory_log))
    for entry in reversed(entries[-200:]):
        if not _is_useful_lesson(entry):
            continue
        if keywords and not _entry_matches_keywords(entry, keywords):
            continue
        score = _score_lesson(entry, keywords)
        if not keywords and str(entry.get("category", "")).lower() != "learning":
            continue

        snippet = _lesson_snippet(entry)
        if not snippet or snippet in seen:
            continue
        seen.add(snippet)
        candidates.append(
            LessonHint(
                title=normalize_text(str(entry.get("title", "")), limit=120),
                snippet=snippet,
                category=str(entry.get("category", "")),
                tags=tuple(str(tag) for tag in entry.get("tags", [])),
                timestamp=str(entry.get("timestamp", "")),
                score=score,
            )
        )

    ordered = sorted(
        candidates,
        key=lambda item: (item.score, item.timestamp),
        reverse=True,
    )
    return ordered[:limit]


def render_session_start_report(project_root: Path) -> str:
    paths = resolve_thumbgate_paths(project_root)
    branch = _run_git(["branch", "--show-current"], project_root) or "unknown"
    counts = read_feedback_counts(project_root)
    lessons = select_relevant_lessons(project_root, limit=2)

    lines = [
        "ThumbGate:",
        f"  Shared feedback dir: {paths.feedback_dir}",
        f"  Branch/worktree: {branch} | {paths.project_root.name}",
        "  Feedback summary:"
        f" {counts['total']} total ({counts['positive']} positive / {counts['negative']} negative)",
    ]

    if lessons:
        lines.append("  Recent useful lessons:")
        for lesson in lessons:
            lines.append(f"  - {lesson.snippet}")
    else:
        lines.append("  Recent useful lessons: none yet")

    return "\n".join(lines)
