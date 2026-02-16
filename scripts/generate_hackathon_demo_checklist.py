#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def file_nonempty(path: Path) -> bool:
    return path.exists() and path.is_file() and path.stat().st_size > 0


def contains(path: Path, needle: str) -> bool:
    if not file_nonempty(path):
        return False
    text = path.read_text(encoding="utf-8", errors="ignore")
    return needle in text


def checkbox(ok: bool) -> str:
    return "[x]" if ok else "[ ]"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate judge-ready Tetrate demo checklist.")
    parser.add_argument("--artifact-dir", default="artifacts/tars", help="TARS artifact directory")
    parser.add_argument("--out", default="", help="Output markdown path")
    args = parser.parse_args()

    artifact_dir = Path(args.artifact_dir)
    out = Path(args.out) if args.out else artifact_dir / "judge_demo_checklist.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    env_status = artifact_dir / "env_status.txt"
    smoke_response = artifact_dir / "smoke_response.json"
    smoke_metrics = artifact_dir / "smoke_metrics.txt"
    resilience = artifact_dir / "resilience_report.txt"
    retrieval = artifact_dir / "retrieval_report.txt"
    summary = artifact_dir / "submission_summary.md"

    checks: list[tuple[str, bool]] = [
        ("Gateway environment captured", file_nonempty(env_status)),
        ("Smoke response recorded", file_nonempty(smoke_response)),
        ("Smoke response includes completion choices", contains(smoke_response, '"choices"')),
        ("Resilience report recorded", file_nonempty(resilience)),
        (
            "Resilience report observed error-path signal",
            contains(resilience, "has_error_field=true"),
        ),
        ("Retrieval report recorded", file_nonempty(retrieval)),
        ("Submission summary generated", file_nonempty(summary)),
        ("Latency/cost metrics captured", file_nonempty(smoke_metrics)),
    ]

    lines: list[str] = []
    lines.append("# Judge Demo Checklist")
    lines.append("")
    lines.append("## Must-Have Evidence")
    for label, ok in checks:
        lines.append(f"- {checkbox(ok)} {label}")
    lines.append("")
    lines.append("## Claim -> Evidence Mapping")
    lines.append(f"- Routed model call works -> `{smoke_response}`")
    lines.append(f"- Failure path is handled -> `{resilience}`")
    lines.append(f"- Retrieval/memory readiness -> `{retrieval}`")
    lines.append(f"- Config + run summary -> `{env_status}`, `{summary}`")
    lines.append("")
    lines.append("## Live Demo Sequence")
    lines.append("1. Open `submission_summary.md` and state the claims.")
    lines.append("2. Show `smoke_response.json` and point to completion choices.")
    lines.append("3. Show `resilience_report.txt` and explain fallback/error-path behavior.")
    lines.append("4. Show `retrieval_report.txt` and describe memory/retrieval readiness.")
    lines.append("5. Show `smoke_metrics.txt` for latency/token/cost context.")
    lines.append("")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"ok: demo checklist generated -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
