"""
Quick CLI to exercise the OpenAI Agents SDK supervisor.

Example:
    python scripts/run_agents_sdk_example.py --prompt "Give me a quick trading take on AAPL."
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.openai_agents import run_supervisor_sync


def main() -> None:
    parser = argparse.ArgumentParser(description="Run OpenAI Agents SDK trading supervisor.")
    parser.add_argument(
        "--prompt",
        default="Give me a quick trading take on AAPL with risk and execution preview.",
        help="User prompt to send to the supervisor.",
    )
    parser.add_argument(
        "--session",
        type=Path,
        default=None,
        help="Optional path to persist the agent session (SQLite).",
    )
    args = parser.parse_args()

    result = run_supervisor_sync(args.prompt, args.session)

    print("=== Final Output ===")
    print(getattr(result, "final_output", result))

    trace_id = getattr(result, "trace_id", None)
    if trace_id:
        print("\ntrace_id:", trace_id)


if __name__ == "__main__":
    main()
