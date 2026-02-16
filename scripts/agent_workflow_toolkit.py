#!/usr/bin/env python3
"""Agentic terminal workflow toolkit.

This script operationalizes high-ROI terminal patterns for agentic workflows:
1) ZSH shortcut bootstrap (single-letter aliases/functions, quick reload, function edit)
2) AI-friendly log slimming with redaction
3) Context bundling with token-aware limits
4) Daily retrospective capture with optional RAG lesson sync
5) Planner/executor command chaining for autonomous task execution
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path

DEFAULT_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BUNDLE_TOKEN_BUDGET = 6000
DEFAULT_BUNDLE_FILE_CHAR_LIMIT = 12000
DEFAULT_LOG_LINE_BUDGET = 300
DEFAULT_LOG_CHAR_BUDGET = 16000

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")
TIMESTAMP_PATTERNS = [
    re.compile(r"^\d{4}-\d{2}-\d{2}[ T][0-9:.+-Z]+\s*"),
    re.compile(r"^\[[0-9]{4}-[0-9]{2}-[0-9]{2}[ T][0-9:.+-Z]+\]\s*"),
]
LOG_LEVEL_RE = re.compile(r"\b(TRACE|DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL)\b")
REDACTION_PATTERNS = [
    re.compile(
        r"(?i)\b(api[_-]?key|token|secret|password)\b([\"']?\s*[:=]\s*[\"']?)([A-Za-z0-9._\-/+=]{4,})"
    ),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-/+=]{8,}"),
    re.compile(r"\bsk-[A-Za-z0-9]{10,}\b"),
]

LOG_LEVEL_SHORT = {
    "TRACE": "T",
    "DEBUG": "D",
    "INFO": "I",
    "WARNING": "W",
    "WARN": "W",
    "ERROR": "E",
    "CRITICAL": "C",
}


@dataclass
class BundleStats:
    included_sections: int
    skipped_sections: int
    approx_tokens: int
    max_tokens: int


@dataclass
class ChainTaskResult:
    index: int
    task: str
    return_code: int
    stdout: str
    stderr: str


@dataclass
class ChainRunSummary:
    run_id: str
    planner_command: str
    executor_command: str
    task_count: int
    failed_tasks: int
    dry_run: bool
    planner_return_code: int


@dataclass
class RetroCapture:
    wins: list[str]
    frictions: list[str]
    actions: list[str]


def estimate_tokens(text: str) -> int:
    """Cheap token estimate for budgeting context payloads."""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def _strip_timestamps(line: str) -> str:
    for pattern in TIMESTAMP_PATTERNS:
        line = pattern.sub("", line, count=1)
    return line


def normalize_log_line(
    line: str,
    *,
    strip_timestamps: bool = True,
    redact_sensitive: bool = True,
) -> str:
    """Normalize one log line for agent-friendly compact context."""
    compact = ANSI_ESCAPE_RE.sub("", line).strip()
    if not compact:
        return ""

    if strip_timestamps:
        compact = _strip_timestamps(compact).strip()

    compact = LOG_LEVEL_RE.sub(lambda m: LOG_LEVEL_SHORT[m.group(1)], compact)

    if redact_sensitive:
        for pattern in REDACTION_PATTERNS:
            if pattern.pattern.startswith("(?i)\\b(api"):
                compact = pattern.sub(r"\1\2[REDACTED]", compact)
            elif "bearer" in pattern.pattern.lower():
                compact = pattern.sub("bearer [REDACTED]", compact)
            else:
                compact = pattern.sub("[REDACTED]", compact)

    compact = re.sub(r"\s+", " ", compact).strip()
    return compact


def _compress_repeated_lines(lines: list[str]) -> list[str]:
    if not lines:
        return []

    compressed: list[str] = []
    current = lines[0]
    count = 1
    for line in lines[1:]:
        if line == current:
            count += 1
            continue
        compressed.append(f"{current} (x{count})" if count > 1 else current)
        current = line
        count = 1
    compressed.append(f"{current} (x{count})" if count > 1 else current)
    return compressed


def slim_log_text(
    raw_text: str,
    *,
    max_lines: int = DEFAULT_LOG_LINE_BUDGET,
    max_chars: int = DEFAULT_LOG_CHAR_BUDGET,
    strip_timestamps: bool = True,
    redact_sensitive: bool = True,
) -> str:
    """Slim noisy logs into concise AI-ready context."""
    normalized = [
        normalize_log_line(
            line,
            strip_timestamps=strip_timestamps,
            redact_sensitive=redact_sensitive,
        )
        for line in raw_text.splitlines()
    ]
    normalized = [line for line in normalized if line]
    normalized = _compress_repeated_lines(normalized)

    if max_lines > 0 and len(normalized) > max_lines:
        normalized = normalized[-max_lines:]

    output = "\n".join(normalized)
    if max_chars > 0 and len(output) > max_chars:
        tail = output[-max_chars:]
        newline_index = tail.find("\n")
        if newline_index >= 0:
            tail = tail[newline_index + 1 :]
        output = "...trimmed...\n" + tail
    return output.strip() + ("\n" if output else "")


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _render_block(content: str, *, line_numbers: bool) -> str:
    if not line_numbers:
        return content
    lines = content.splitlines()
    return "\n".join(f"{index:5d}: {line}" for index, line in enumerate(lines, 1))


def _coerce_relative_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path)


def build_context_bundle(
    *,
    sections: list[tuple[str, str]],
    max_tokens: int = DEFAULT_BUNDLE_TOKEN_BUDGET,
    max_chars_per_section: int = DEFAULT_BUNDLE_FILE_CHAR_LIMIT,
    line_numbers: bool = False,
) -> tuple[str, BundleStats]:
    """Build a token-aware markdown context bundle."""
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    header = [
        "# Agent Context Bundle",
        "",
        f"- Generated (UTC): `{now_utc}`",
        f"- Max Tokens: `{max_tokens}`",
        "",
    ]
    chunks: list[str] = ["\n".join(header)]
    used_tokens = estimate_tokens(chunks[0])
    included = 0
    skipped = 0

    for name, raw_content in sections:
        clipped = raw_content
        truncated = False
        if max_chars_per_section > 0 and len(clipped) > max_chars_per_section:
            clipped = clipped[:max_chars_per_section]
            truncated = True

        body = _render_block(clipped, line_numbers=line_numbers)
        section_lines = [
            f"## {name}",
            "",
            "```text",
            body,
            "```",
        ]
        if truncated:
            section_lines.extend(["", "_Truncated by per-section character budget._"])
        section_lines.append("")
        section_text = "\n".join(section_lines)
        section_tokens = estimate_tokens(section_text)

        if max_tokens > 0 and used_tokens + section_tokens > max_tokens:
            skipped += 1
            continue

        chunks.append(section_text)
        used_tokens += section_tokens
        included += 1

    stats = BundleStats(
        included_sections=included,
        skipped_sections=skipped,
        approx_tokens=used_tokens,
        max_tokens=max_tokens,
    )
    chunks.extend(
        [
            "## Bundle Stats",
            "",
            f"- Included Sections: `{stats.included_sections}`",
            f"- Skipped Sections: `{stats.skipped_sections}`",
            f"- Approx Tokens: `{stats.approx_tokens}`",
            "",
        ]
    )
    return "\n".join(chunks), stats


def parse_plan_tasks(plan_text: str, *, max_tasks: int = 8) -> list[str]:
    """Extract executable tasks from markdown or plaintext plans."""
    task_patterns = [
        re.compile(r"^\s*[-*]\s+\[[ xX]\]\s+(.+?)\s*$"),
        re.compile(r"^\s*\d+[.)]\s+(.+?)\s*$"),
        re.compile(r"^\s*[-*]\s+(.+?)\s*$"),
    ]
    tasks: list[str] = []
    for line in plan_text.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        for pattern in task_patterns:
            match = pattern.match(text)
            if match:
                task = match.group(1).strip()
                if task and len(task) >= 3 and task.lower() not in {"done", "todo"}:
                    tasks.append(task.rstrip("."))
                break
        if len(tasks) >= max_tasks:
            break

    if tasks:
        return tasks

    fallback = [line.strip() for line in plan_text.splitlines() if line.strip()]
    return fallback[:max_tasks] if fallback else []


def _run_command(command: str, *, prompt: str, cwd: Path) -> tuple[int, str, str]:
    args = shlex.split(command)
    if not args:
        return 1, "", "empty command"
    result = subprocess.run(
        args,
        input=prompt,
        text=True,
        capture_output=True,
        check=False,
        cwd=str(cwd),
    )
    return result.returncode, result.stdout, result.stderr


def _default_plan(task: str) -> str:
    return "\n".join(
        [
            "# Execution Plan",
            "",
            f"1. Clarify acceptance criteria for: {task}",
            "2. Gather the minimal repo context needed to implement safely",
            "3. Implement targeted code changes with tests",
            "4. Run lint + tests and capture evidence",
            "5. Summarize outcomes and next hardening step",
            "",
        ]
    )


def run_chain(
    *,
    task: str,
    planner_command: str,
    executor_command: str,
    output_dir: Path,
    workdir: Path,
    max_tasks: int = 8,
    dry_run: bool = False,
) -> tuple[int, Path]:
    """Run planner/executor chaining and persist artifacts."""
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    planner_return_code = 0
    planner_stderr = ""
    if dry_run:
        plan_text = _default_plan(task)
    else:
        planner_prompt = "\n".join(
            [
                "Create an execution plan with concrete numbered tasks.",
                "Keep tasks atomic and implementation-oriented.",
                "",
                f"Primary goal: {task}",
            ]
        )
        planner_return_code, planner_stdout, planner_stderr = _run_command(
            planner_command,
            prompt=planner_prompt,
            cwd=workdir,
        )
        plan_text = planner_stdout.strip() if planner_stdout.strip() else _default_plan(task)

    tasks = parse_plan_tasks(plan_text, max_tasks=max_tasks)
    if not tasks:
        tasks = [task]

    plan_md = [
        "# Planner Output",
        "",
        f"- Run ID: `{run_id}`",
        f"- Planner Command: `{planner_command}`",
        f"- Planner Return Code: `{planner_return_code}`",
        "",
        "## Plan",
        "",
        plan_text.rstrip(),
        "",
    ]
    if planner_stderr.strip():
        plan_md.extend(["## Planner Stderr", "", "```text", planner_stderr.strip(), "```", ""])
    (run_dir / "plan.md").write_text("\n".join(plan_md), encoding="utf-8")

    task_results: list[ChainTaskResult] = []
    for index, task_text in enumerate(tasks, 1):
        if dry_run:
            task_results.append(
                ChainTaskResult(
                    index=index,
                    task=task_text,
                    return_code=0,
                    stdout="DRY RUN: executor skipped.",
                    stderr="",
                )
            )
            continue

        executor_prompt = "\n".join(
            [
                f"Task {index}/{len(tasks)}",
                f"Objective: {task_text}",
                "",
                "Global goal:",
                task,
                "",
                "Plan context:",
                plan_text,
            ]
        )
        code, stdout, stderr = _run_command(executor_command, prompt=executor_prompt, cwd=workdir)
        task_results.append(
            ChainTaskResult(
                index=index,
                task=task_text,
                return_code=code,
                stdout=stdout.strip(),
                stderr=stderr.strip(),
            )
        )

    failed_tasks = sum(1 for item in task_results if item.return_code != 0)
    summary = ChainRunSummary(
        run_id=run_id,
        planner_command=planner_command,
        executor_command=executor_command,
        task_count=len(task_results),
        failed_tasks=failed_tasks,
        dry_run=dry_run,
        planner_return_code=planner_return_code,
    )

    execution_lines = ["# Executor Output", ""]
    for result in task_results:
        execution_lines.extend(
            [
                f"## Task {result.index}",
                f"- Description: {result.task}",
                f"- Return Code: `{result.return_code}`",
                "",
                "### Stdout",
                "```text",
                result.stdout or "<empty>",
                "```",
                "",
                "### Stderr",
                "```text",
                result.stderr or "<empty>",
                "```",
                "",
            ]
        )
    (run_dir / "execution.md").write_text("\n".join(execution_lines), encoding="utf-8")
    (run_dir / "summary.json").write_text(json.dumps(asdict(summary), indent=2), encoding="utf-8")

    exit_code = 1 if planner_return_code != 0 or failed_tasks > 0 else 0
    return exit_code, run_dir


def build_zsh_snippet(*, toolkit_path: Path) -> str:
    """Generate copy/paste-ready zsh helper snippet."""
    safe_toolkit = str(toolkit_path)
    return "\n".join(
        [
            "# ---- agent workflow toolkit ----",
            "for __agent_fn in x p s funked bundlectx slimlog retroday chainagents runlog; do",
            '  unalias "$__agent_fn" 2>/dev/null || true',
            "done",
            "unset __agent_fn",
            "",
            "x() {",
            '  local cmd="${AGENT_FAST_CMD:-codex}"',
            '  if [[ -n "${AGENT_FAST_FLAGS:-}" ]]; then',
            '    $cmd ${=AGENT_FAST_FLAGS} "$@"',
            "  else",
            '    $cmd "$@"',
            "  fi",
            "}",
            "",
            "p() {",
            '  local cmd="${AGENT_PLANNER_CMD:-claude}"',
            '  if [[ -n "${AGENT_PLANNER_FLAGS:-}" ]]; then',
            '    $cmd ${=AGENT_PLANNER_FLAGS} "$@"',
            "  else",
            '    $cmd "$@"',
            "  fi",
            "}",
            "",
            "funked() {",
            '  local target="$1"',
            '  local rc="${ZDOTDIR:-$HOME}/.zshrc"',
            '  if [[ -z "$target" ]]; then',
            '    echo "usage: funked <alias-or-function>"',
            "    return 1",
            "  fi",
            "  local line",
            '  line=$(grep -nE "^(alias[[:space:]]+${target}=|${target}[[:space:]]*\\(\\)|function[[:space:]]+${target})" "$rc" | head -n1 | cut -d: -f1)',
            '  ${EDITOR:-vi} "+${line:-1}" "$rc"',
            "}",
            "",
            's() { source "${ZDOTDIR:-$HOME}/.zshrc"; }',
            "",
            "bundlectx() {",
            f'  python3 "{safe_toolkit}" bundle "$@"',
            "}",
            "",
            "slimlog() {",
            f'  python3 "{safe_toolkit}" slim-logs "$@"',
            "}",
            "",
            "retroday() {",
            f'  python3 "{safe_toolkit}" retro "$@"',
            "}",
            "",
            "chainagents() {",
            f'  python3 "{safe_toolkit}" chain "$@"',
            "}",
            "",
            'runlog() { "$@" 2>&1 | slimlog; }',
            "# ---- /agent workflow toolkit ----",
            "",
        ]
    )


def _parse_prefixed_items(raw_text: str, prefix: str) -> list[str]:
    pattern = re.compile(rf"^\s*{re.escape(prefix)}\s*[:\-]\s*(.+?)\s*$", re.IGNORECASE)
    items: list[str] = []
    for line in raw_text.splitlines():
        match = pattern.match(line)
        if match:
            value = match.group(1).strip()
            if value:
                items.append(value)
    return items


def build_retro_markdown(
    *,
    entry_date: date,
    capture: RetroCapture,
    conversation_excerpt: str = "",
) -> str:
    lines: list[str] = []
    lines.extend(
        [
            "# Daily Agentic Retrospective",
            "",
            f"- Date: `{entry_date.isoformat()}`",
            "",
            "## Wins",
        ]
    )
    lines.extend([f"- {item}" for item in capture.wins] or ["- none captured"])
    lines.extend(["", "## Frictions"])
    lines.extend([f"- {item}" for item in capture.frictions] or ["- none captured"])
    lines.extend(["", "## Actions for Next Session"])
    lines.extend([f"- {item}" for item in capture.actions] or ["- none captured"])

    excerpt = conversation_excerpt.strip()
    if excerpt:
        trimmed = excerpt[:2000]
        lines.extend(["", "## Conversation Excerpt", "", "```text", trimmed, "```"])

    lines.append("")
    return "\n".join(lines)


def _build_rag_lesson_markdown(entry_date: date, retro_markdown: str) -> str:
    tag_line = "`agentic-workflow`, `automation`, `terminal`, `continuous-improvement`"
    return "\n".join(
        [
            f"# LL-Agentic-Retro-{entry_date.strftime('%Y%m%d')}",
            "",
            "Source: daily retro automation",
            "",
            retro_markdown.strip(),
            "",
            "Tags:",
            tag_line,
            "",
        ]
    )


def write_retro_files(
    *,
    repo_root: Path,
    entry_date: date,
    retro_markdown: str,
) -> tuple[Path, Path]:
    artifact_path = repo_root / "artifacts" / "devloop" / "retros" / f"{entry_date.isoformat()}.md"
    rag_path = (
        repo_root
        / "rag_knowledge"
        / "lessons_learned"
        / f"ll_agentic_retro_{entry_date.strftime('%Y%m%d')}.md"
    )
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    rag_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(retro_markdown, encoding="utf-8")
    rag_path.write_text(_build_rag_lesson_markdown(entry_date, retro_markdown), encoding="utf-8")
    return artifact_path, rag_path


def _read_stdin_if_available() -> str:
    if sys.stdin.isatty():
        return ""
    return sys.stdin.read()


def _parse_date(raw: str) -> date:
    return datetime.strptime(raw, "%Y-%m-%d").date()


def _dedupe_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        clean = value.strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        output.append(clean)
    return output


def cmd_zsh_snippet(args: argparse.Namespace) -> int:
    toolkit_path = Path(args.toolkit_path).resolve()
    print(build_zsh_snippet(toolkit_path=toolkit_path))
    return 0


def cmd_slim_logs(args: argparse.Namespace) -> int:
    text_fragments: list[str] = []
    for path_str in args.input_paths:
        path = Path(path_str)
        if not path.exists():
            print(f"warning: missing input file -> {path}", file=sys.stderr)
            continue
        text_fragments.append(_load_text(path))

    if not text_fragments:
        stdin_payload = _read_stdin_if_available()
        if stdin_payload:
            text_fragments.append(stdin_payload)

    if not text_fragments:
        print("error: no log input provided (use --in or pipe stdin)", file=sys.stderr)
        return 1

    slimmed = slim_log_text(
        "\n".join(text_fragments),
        max_lines=args.max_lines,
        max_chars=args.max_chars,
        strip_timestamps=not args.keep_timestamps,
        redact_sensitive=not args.no_redact,
    )
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(slimmed, encoding="utf-8")
        print(f"ok: slim log written -> {out_path}")
    print(slimmed, end="")
    return 0


def _read_file_list(path: Path) -> list[str]:
    values: list[str] = []
    for raw_line in _load_text(path).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        values.append(line)
    return values


def cmd_bundle(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    section_inputs: list[tuple[str, str]] = []

    raw_paths = list(args.paths)
    if args.file_list:
        file_list_path = Path(args.file_list)
        if not file_list_path.exists():
            print(f"error: file list not found -> {file_list_path}", file=sys.stderr)
            return 1
        raw_paths.extend(_read_file_list(file_list_path))

    for raw in raw_paths:
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = repo_root / candidate
        if not candidate.exists():
            print(f"warning: skipped missing path -> {raw}", file=sys.stderr)
            continue
        if candidate.is_dir():
            print(f"warning: skipped directory path -> {raw}", file=sys.stderr)
            continue
        section_name = _coerce_relative_path(candidate, repo_root)
        section_inputs.append((section_name, _load_text(candidate)))

    if args.include_stdin:
        stdin_payload = _read_stdin_if_available()
        if stdin_payload:
            section_inputs.append((args.stdin_name, stdin_payload))

    if not section_inputs:
        print("error: no bundle inputs provided", file=sys.stderr)
        return 1

    bundle_text, stats = build_context_bundle(
        sections=section_inputs,
        max_tokens=args.max_tokens,
        max_chars_per_section=args.max_file_chars,
        line_numbers=args.line_numbers,
    )

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(bundle_text, encoding="utf-8")
        print(f"ok: bundle written -> {out_path}")

    print(bundle_text, end="")
    if args.json_stats:
        print(json.dumps(asdict(stats), indent=2))
    return 0


def cmd_retro(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    entry_date = _parse_date(args.date) if args.date else datetime.now(timezone.utc).date()
    stdin_payload = _read_stdin_if_available() if args.include_stdin else ""

    explicit_wins = list(args.win)
    explicit_frictions = list(args.friction)
    explicit_actions = list(args.action)
    parsed_wins = _parse_prefixed_items(stdin_payload, "WIN")
    parsed_frictions = _parse_prefixed_items(stdin_payload, "FRICTION")
    parsed_actions = _parse_prefixed_items(stdin_payload, "ACTION")

    capture = RetroCapture(
        wins=_dedupe_keep_order(explicit_wins + parsed_wins),
        frictions=_dedupe_keep_order(explicit_frictions + parsed_frictions),
        actions=_dedupe_keep_order(explicit_actions + parsed_actions),
    )

    conversation_excerpt = ""
    if args.conversation_export:
        export_path = Path(args.conversation_export)
        if export_path.exists():
            conversation_excerpt = _load_text(export_path)
        else:
            print(f"warning: conversation export missing -> {export_path}", file=sys.stderr)

    retro_markdown = build_retro_markdown(
        entry_date=entry_date,
        capture=capture,
        conversation_excerpt=conversation_excerpt or stdin_payload,
    )
    artifact_path, rag_path = write_retro_files(
        repo_root=repo_root,
        entry_date=entry_date,
        retro_markdown=retro_markdown,
    )
    print(f"ok: retro artifact -> {artifact_path}")
    print(f"ok: rag lesson -> {rag_path}")
    print(retro_markdown, end="")
    return 0


def cmd_chain(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    output_dir = Path(args.out_dir).resolve()
    workdir = Path(args.workdir).resolve() if args.workdir else repo_root
    planner_command = args.planner_cmd.strip()
    executor_command = args.executor_cmd.strip()

    if not planner_command or not executor_command:
        print("error: planner and executor commands must be non-empty", file=sys.stderr)
        return 1

    exit_code, run_dir = run_chain(
        task=args.task,
        planner_command=planner_command,
        executor_command=executor_command,
        output_dir=output_dir,
        workdir=workdir,
        max_tasks=args.max_tasks,
        dry_run=args.dry_run,
    )
    print(f"ok: chain artifacts -> {run_dir}")
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    print(json.dumps(summary, indent=2))
    return exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agentic terminal workflow toolkit")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_zsh = subparsers.add_parser(
        "zsh-snippet",
        help="Generate zsh helper snippet (x, p, funked, s, and toolkit wrappers).",
    )
    parser_zsh.add_argument(
        "--toolkit-path",
        default=str(Path(__file__).resolve()),
        help="Absolute path to this toolkit script.",
    )
    parser_zsh.set_defaults(handler=cmd_zsh_snippet)

    parser_logs = subparsers.add_parser("slim-logs", help="Slim noisy logs for AI context.")
    parser_logs.add_argument(
        "--in",
        dest="input_paths",
        action="append",
        default=[],
        help="Input log file path (repeatable). If omitted, reads stdin.",
    )
    parser_logs.add_argument("--out", default="", help="Optional output path for slimmed logs.")
    parser_logs.add_argument(
        "--max-lines",
        type=int,
        default=DEFAULT_LOG_LINE_BUDGET,
        help=f"Maximum lines in output (default: {DEFAULT_LOG_LINE_BUDGET}).",
    )
    parser_logs.add_argument(
        "--max-chars",
        type=int,
        default=DEFAULT_LOG_CHAR_BUDGET,
        help=f"Maximum characters in output (default: {DEFAULT_LOG_CHAR_BUDGET}).",
    )
    parser_logs.add_argument(
        "--keep-timestamps",
        action="store_true",
        help="Preserve timestamps in output.",
    )
    parser_logs.add_argument(
        "--no-redact",
        action="store_true",
        help="Disable credential/token redaction.",
    )
    parser_logs.set_defaults(handler=cmd_slim_logs)

    parser_bundle = subparsers.add_parser(
        "bundle",
        help="Build token-budgeted markdown bundle from files/stdin.",
    )
    parser_bundle.add_argument("paths", nargs="*", help="File paths to include in bundle.")
    parser_bundle.add_argument(
        "--file-list",
        default="",
        help="Optional newline-delimited file list to include.",
    )
    parser_bundle.add_argument(
        "--repo-root",
        default=str(DEFAULT_REPO_ROOT),
        help="Repo root for resolving relative paths.",
    )
    parser_bundle.add_argument("--out", default="", help="Optional bundle output path.")
    parser_bundle.add_argument(
        "--max-tokens",
        type=int,
        default=DEFAULT_BUNDLE_TOKEN_BUDGET,
        help=f"Approx token budget (default: {DEFAULT_BUNDLE_TOKEN_BUDGET}).",
    )
    parser_bundle.add_argument(
        "--max-file-chars",
        type=int,
        default=DEFAULT_BUNDLE_FILE_CHAR_LIMIT,
        help=f"Max characters per file section (default: {DEFAULT_BUNDLE_FILE_CHAR_LIMIT}).",
    )
    parser_bundle.add_argument(
        "--line-numbers",
        action="store_true",
        help="Add line numbers to section content.",
    )
    parser_bundle.add_argument(
        "--include-stdin",
        action="store_true",
        help="Include piped stdin as an additional section.",
    )
    parser_bundle.add_argument(
        "--stdin-name",
        default="stdin.txt",
        help="Section name for stdin payload when --include-stdin is used.",
    )
    parser_bundle.add_argument(
        "--json-stats",
        action="store_true",
        help="Emit bundle stats JSON after bundle output.",
    )
    parser_bundle.set_defaults(handler=cmd_bundle)

    parser_retro = subparsers.add_parser(
        "retro",
        help="Capture daily retrospective and sync to artifacts + RAG lessons.",
    )
    parser_retro.add_argument(
        "--repo-root",
        default=str(DEFAULT_REPO_ROOT),
        help="Repo root where artifacts/rag paths exist.",
    )
    parser_retro.add_argument(
        "--date",
        default="",
        help="Date in YYYY-MM-DD. Default is current UTC date.",
    )
    parser_retro.add_argument("--win", action="append", default=[], help="Win bullet (repeatable).")
    parser_retro.add_argument(
        "--friction",
        action="append",
        default=[],
        help="Friction bullet (repeatable).",
    )
    parser_retro.add_argument(
        "--action",
        action="append",
        default=[],
        help="Action bullet for next session (repeatable).",
    )
    parser_retro.add_argument(
        "--conversation-export",
        default="",
        help="Optional markdown/text export file to attach as excerpt.",
    )
    parser_retro.add_argument(
        "--include-stdin",
        action="store_true",
        help="Parse WIN:/FRICTION:/ACTION: items from stdin and include excerpt.",
    )
    parser_retro.set_defaults(handler=cmd_retro)

    parser_chain = subparsers.add_parser(
        "chain",
        help="Run planner/executor workflow and persist run artifacts.",
    )
    parser_chain.add_argument("--task", required=True, help="High-level task objective.")
    parser_chain.add_argument(
        "--planner-cmd",
        default="cat",
        help="Planner command (stdin prompt -> stdout plan).",
    )
    parser_chain.add_argument(
        "--executor-cmd",
        default="cat",
        help="Executor command (stdin task prompt -> stdout result).",
    )
    parser_chain.add_argument(
        "--out-dir",
        default=str(DEFAULT_REPO_ROOT / "artifacts" / "agentic_runs"),
        help="Directory for run artifacts.",
    )
    parser_chain.add_argument(
        "--repo-root",
        default=str(DEFAULT_REPO_ROOT),
        help="Repo root context.",
    )
    parser_chain.add_argument(
        "--workdir",
        default="",
        help="Working directory for planner/executor commands.",
    )
    parser_chain.add_argument(
        "--max-tasks",
        type=int,
        default=8,
        help="Maximum parsed tasks to execute.",
    )
    parser_chain.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip external commands and simulate execution.",
    )
    parser_chain.set_defaults(handler=cmd_chain)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 1
    try:
        return int(handler(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
