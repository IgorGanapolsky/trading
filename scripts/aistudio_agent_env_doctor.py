#!/usr/bin/env python3
"""CLI for AI Studio agent-environment FORMAT doctor (trading).

Exit 0 only when every dimension ok=true.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ops.agent_environment_doctor import diagnose_agent_environment  # noqa: E402


def _split(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [p.strip() for p in raw.replace("|", ",").split(",") if p.strip()]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=str(ROOT), help="Repo root to scan")
    p.add_argument(
        "--tools",
        default="context_gist,entry_challenges,system_health_check,spy_put_credit_dry_run,aistudio_agent_env_doctor",
        help="Comma/pipe-separated proposed tools",
    )
    p.add_argument(
        "--domains",
        default="",
        help="Comma/pipe-separated proposed egress domains (empty = offline)",
    )
    p.add_argument(
        "--stop-when",
        default="doctor exits; do not call Gemini sandbox",
    )
    p.add_argument(
        "--out-of-scope",
        default="Antigravity; Vertex Agent Builder; billed AI Studio runs",
    )
    p.add_argument(
        "--acs",
        default="tests pass|CLI fail-closed on undeclared tool/domain",
        help="Acceptance criteria (≥1)",
    )
    args = p.parse_args(argv)
    report = diagnose_agent_environment(
        args.root,
        proposed_tools=_split(args.tools),
        proposed_domains=_split(args.domains),
        stop_when=args.stop_when,
        out_of_scope=args.out_of_scope,
        acceptance_criteria=_split(args.acs),
    )
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
