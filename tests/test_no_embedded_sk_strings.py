from __future__ import annotations

import re
from pathlib import Path


# Heuristic: catch accidentally committed "sk-..." style API keys (OpenAI/Tetrate/etc).
# We require a long tail to avoid tripping on short examples in docs/tests.
SUSPICIOUS_SK_KEY_RE = re.compile(r"sk-[A-Za-z0-9][A-Za-z0-9+/=_\\-\\.]{30,}")


def _iter_text_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_file():
            files.append(path)
            continue
        if not path.is_dir():
            continue
        for candidate in path.rglob("*"):
            if not candidate.is_file():
                continue
            if candidate.is_symlink():
                continue
            # Skip common binary/artifact extensions.
            if candidate.suffix.lower() in {
                ".png",
                ".jpg",
                ".jpeg",
                ".gif",
                ".pdf",
                ".zip",
                ".gz",
                ".tar",
                ".db",
                ".sqlite",
                ".pyc",
                ".pkl",
            }:
                continue
            files.append(candidate)
    return files


def test_no_embedded_sk_api_keys() -> None:
    scan_roots = [
        Path("src"),
        Path("scripts"),
        Path("docs"),
        Path("cloudflare-workers"),
        Path(".github"),
        Path(".env.example"),
        Path("AGENTS.md"),
        Path("README.md"),
    ]

    offenders: list[str] = []
    for file_path in _iter_text_files(scan_roots):
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if SUSPICIOUS_SK_KEY_RE.search(text):
            offenders.append(str(file_path))

    assert offenders == [], (
        "Potential embedded API key(s) detected (pattern: sk-<...>):\n" + "\n".join(offenders)
    )
