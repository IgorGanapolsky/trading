import asyncio
import logging
from collections.abc import Callable
from typing import Any

from src.adk.core import Agent

logger = logging.getLogger(__name__)


class SequentialAgent(Agent):
    def __init__(self, name: str, agents: list[Agent]):
        super().__init__(name)
        self.agents = agents

    async def run(self, input_data: Any, context: dict[str, Any]) -> Any:
        current_input = input_data
        logger.info(f"SequentialAgent {self.name} starting with {len(self.agents)} steps.")

        for i, agent in enumerate(self.agents):
            logger.info(
                f"SequentialAgent {self.name} step {i + 1}/{len(self.agents)}: {agent.name}"
            )
            current_input = await agent.run(current_input, context)

        return current_input


class ParallelAgent(Agent):
    def __init__(self, name: str, agents: dict[str, Agent], max_concurrency: int = 1):
        super().__init__(name)
        self.agents = agents
        self.max_concurrency = max_concurrency

    async def run(self, input_data: Any, context: dict[str, Any]) -> dict[str, Any]:
        logger.info(
            f"ParallelAgent {self.name} starting {len(self.agents)} tasks with max_concurrency={self.max_concurrency}."
        )

        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def run_with_semaphore(agent: Agent):
            async with semaphore:
                return await agent.run(input_data, context)

        keys = list(self.agents.keys())
        tasks = [run_with_semaphore(agent) for agent in self.agents.values()]

        results = await asyncio.gather(*tasks)

        return dict(zip(keys, results, strict=False))


class LoopAgent(Agent):
    def __init__(
        self, name: str, agent: Agent, condition: Callable[[Any], bool], max_loops: int = 5
    ):
        super().__init__(name)
        self.agent = agent
        self.condition = condition
        self.max_loops = max_loops

    async def run(self, input_data: Any, context: dict[str, Any]) -> Any:
        logger.info(f"LoopAgent {self.name} starting (max_loops={self.max_loops}).")

        current_input = input_data
        for i in range(self.max_loops):
            logger.info(f"LoopAgent {self.name} iteration {i + 1}")
            result = await self.agent.run(current_input, context)

            if self.condition(result):
                logger.info(f"LoopAgent {self.name} condition met.")
                return result

            current_input = result

        logger.warning(f"LoopAgent {self.name} max loops reached without meeting condition.")
        return current_input
