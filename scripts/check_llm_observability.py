#!/usr/bin/env python3
"""
Check effective LLM routing and OpenRouter logging coverage.

This verifies what this process can actually observe:
- direct OpenRouter traffic
- gateway-routed OpenRouter-compatible traffic
- Anthropic-only critical execution coverage
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=PROJECT_ROOT / ".env", override=False)
except (ImportError, AssertionError, Exception):
    pass

from src.observability.llm_observability import (  # noqa: E402
    build_llm_observability_report,
    render_llm_observability_lines,
)


def main() -> int:
    report = build_llm_observability_report()
    icon = {"ok": "✅", "warning": "⚠️", "broken": "❌"}.get(report.status, "❓")

    print("=" * 70)
    print("LLM OBSERVABILITY CHECK")
    print("=" * 70)
    print(f"{icon} {report.summary}")
    for line in render_llm_observability_lines(report):
        print(f"   {line}")

    if report.status == "broken":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
