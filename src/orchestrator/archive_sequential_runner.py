"""
Legacy sequential orchestrator retained for reference.

This module preserves the original agent-framework based runner so we can
compare behaviour or fall back if needed. The new hybrid funnel orchestrator
now lives in `src/orchestrator/main.py`.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from agent_framework import (
    AgentConfig,
    FileStateProvider,
    RunContext,
    RunMode,
    StateProvider,
    TradingAgent,
)
from agent_framework.base import AgentResult
from agents.data_agent import DataAgent

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorConfig:
    """Configuration object used to bootstrap the orchestrator."""

    agents: list[TradingAgent] = field(default_factory=list)
    state_provider: StateProvider = field(
        default_factory=lambda: FileStateProvider(Path("data/system_state.json"))
    )


class NoOpAgent(TradingAgent):
    """
    Placeholder agent used until dedicated implementations are wired in.

    It simply logs the current run mode and succeeds without side effects.
    """

    def __init__(self, agent_name: str) -> None:
        super().__init__(agent_name)

    def execute(self, context: RunContext) -> AgentResult:
        payload = {
            "message": f"{self.agent_name} executed in {context.mode.value} mode.",
            "force": context.force,
        }
        return AgentResult(name=self.agent_name, succeeded=True, payload=payload)


class TradingOrchestrator:
    """Coordinates agent execution and state persistence."""

    def __init__(self, config: OrchestratorConfig) -> None:
        if not config.agents:
            logger.warning("Orchestrator started with no agents configured.")
        self.config = config

    def run_once(self, context: RunContext) -> Iterable[AgentResult]:
        logger.info(
            "Starting orchestrator run (force=%s, mode=%s)",
            context.force,
            context.mode.value,
        )
        state = self.config.state_provider.load()
        context.state_cache["state"] = state
        results: list[AgentResult] = []

        for agent in self.config.agents:
            result = agent.run(context)
            results.append(result)

        updated_state = context.state_cache.get("state", state)
        if updated_state != state:
            logger.debug("Persisting updated state.")
            self.config.state_provider.save(updated_state)

        logger.info("Orchestrator run complete.")
        return results


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the multi-agent trading orchestrator.")
    parser.add_argument(
        "--mode",
        choices=[m.value for m in RunMode],
        default=RunMode.PAPER.value,
        help="Execution mode (live/paper/dry_run).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force execution even if a run already occurred today.",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=Path("data/system_state.json"),
        help="Path to orchestrator state file (default: data/system_state.json).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )

    mode = RunMode(args.mode)
    context = RunContext(
        mode=mode,
        force=args.force,
        config=AgentConfig(),
    )

    orchestrator = TradingOrchestrator(
        OrchestratorConfig(
            agents=[
                DataAgent(),
                NoOpAgent("strategy-agent"),
                NoOpAgent("risk-agent"),
                NoOpAgent("execution-agent"),
                NoOpAgent("audit-agent"),
            ],
            state_provider=FileStateProvider(args.state_file),
        )
    )

    orchestrator.run_once(context)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
