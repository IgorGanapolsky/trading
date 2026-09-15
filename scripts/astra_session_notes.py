#!/usr/bin/env python3
"""Searchable session notes across context windows (GPT-6 Astra FORMAT steal).

InfoQ: Astra Codex keeps notes across windows; prior windows stay searchable
instead of relying only on lossy compaction.

Local: append-only JSONL notes + keyword search. Not OpenAI Codex product.
Not a 1M-token context claim.

EXIT 0 always for report. EXIT 2 with --strict if search required and empty.
"""

from __future__ import annotations

import argparse
import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NOTES = ROOT / "data" / "runtime" / "astra_session_notes.jsonl"

KINDS = frozenset({"requirement", "test_result", "tool_output", "decision", "blocker", "receipt"})


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def append_note(
    *,
    text: str,
    kind: str = "decision",
    window_id: str = "",
    tags: list[str] | None = None,
    path: Path = DEFAULT_NOTES,
) -> dict:
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {sorted(KINDS)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "id": str(uuid.uuid4())[:12],
        "ts": _now(),
        "kind": kind,
        "window_id": window_id or f"win-{_now()[:10]}",
        "tags": tags or [],
        "text": text.strip(),
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def load_notes(*, path: Path = DEFAULT_NOTES) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def search_notes(
    query: str,
    *,
    path: Path = DEFAULT_NOTES,
    kind: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Keyword search across all windows (Astra: prior windows remain searchable)."""
    q = (query or "").strip().lower()
    tokens = [t for t in re.split(r"\W+", q) if t]
    hits = []
    for row in load_notes(path=path):
        if kind and row.get("kind") != kind:
            continue
        blob = f"{row.get('text', '')} {' '.join(row.get('tags') or [])}".lower()
        if not tokens or all(t in blob for t in tokens):
            score = sum(blob.count(t) for t in tokens) if tokens else 1
            hits.append({**row, "score": score})
    hits.sort(key=lambda r: (-r["score"], r.get("ts") or ""))
    return hits[:limit]


def summary(*, path: Path = DEFAULT_NOTES) -> dict:
    notes = load_notes(path=path)
    by_kind: dict[str, int] = {}
    windows = set()
    for n in notes:
        by_kind[n.get("kind") or "unknown"] = by_kind.get(n.get("kind") or "unknown", 0) + 1
        windows.add(n.get("window_id") or "")
    return {
        "ok": True,
        "framework": "astra_session_notes",
        "stolen_format": (
            "GPT-6 Astra / InfoQ — searchable notes across context windows "
            "(not compaction-only; not OpenAI Codex product)"
        ),
        "source": {"infoq": "https://www.infoq.com/news/2026/09/openai-gpt6-astra/"},
        "notes_path": str(path),
        "count": len(notes),
        "windows": len(windows),
        "by_kind": by_kind,
        "ts": _now(),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add", help="append a durable note")
    a.add_argument("--text", required=True)
    a.add_argument("--kind", default="decision", choices=sorted(KINDS))
    a.add_argument("--window-id", default="")
    a.add_argument("--tag", action="append", default=[])
    s = sub.add_parser("search", help="search across all windows")
    s.add_argument("--query", required=True)
    s.add_argument("--kind", default=None, choices=sorted(KINDS))
    s.add_argument("--limit", type=int, default=20)
    s.add_argument("--strict", action="store_true")
    sub.add_parser("summary")
    args = p.parse_args(argv)
    if args.cmd == "add":
        row = append_note(text=args.text, kind=args.kind, window_id=args.window_id, tags=args.tag)
        print(json.dumps(row, indent=2, sort_keys=True))
        return 0
    if args.cmd == "search":
        hits = search_notes(args.query, kind=args.kind, limit=args.limit)
        print(
            json.dumps(
                {"ok": bool(hits), "query": args.query, "hits": hits}, indent=2, sort_keys=True
            )
        )
        if args.strict and not hits:
            return 2
        return 0
    if args.cmd == "summary":
        print(json.dumps(summary(), indent=2, sort_keys=True))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
