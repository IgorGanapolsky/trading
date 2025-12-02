#!/usr/bin/env python3
"""
Kick off the LangSmith dataset regression for the price-action agent.

Example:
    LANGCHAIN_API_KEY=sk-... \
    LANGSMITH_AGENT_EVAL_DATASET=price-action-evals \
    python scripts/langsmith_price_action_eval.py
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from langchain_agents.agents import build_price_action_agent
from langchain_agents.langsmith_support import LangSmithAgentBridge


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the LangSmith dataset regression for the price-action agent."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build the agent but skip the remote evaluation.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print the evaluation response as JSON.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    agent = build_price_action_agent()
    bridge: LangSmithAgentBridge | None = getattr(
        agent, "langsmith_bridge", LangSmithAgentBridge("price-action-agent")
    )

    if args.dry_run:
        print("✅ Dry-run complete. Agent built successfully.")
        return

    try:
        result = bridge.run_dataset_evaluation(agent)
    except Exception as exc:  # pragma: no cover - network call
        logging.error("LangSmith evaluation failed: %s", exc)
        sys.exit(1)

    if args.pretty:
        print(json.dumps(result, indent=2))
    else:
        print(result)


if __name__ == "__main__":
    main()
