import abc
from collections.abc import Callable
from typing import Any


class Agent(abc.ABC):
    """Abstract base class for all agents."""

    def __init__(self, name: str):
        self.name = name

    @abc.abstractmethod
    async def run(self, input_data: Any, context: dict[str, Any]) -> Any:
        """
        Executes the agent's logic.

        Args:
            input_data: The input for this execution step.
            context: Shared context dictionary across the workflow.

        Returns:
            The output of the agent's execution.
        """
        pass

    def as_tool(self, description: str) -> "AgentTool":
        """Wraps this agent as a tool usable by other agents."""
        return AgentTool(agent=self, description=description)


class AgentTool:
    """Wraps an Agent so it can be used as a function/tool by an LLM."""

    def __init__(self, agent: Agent, description: str):
        self.agent = agent
        self.description = description
        self.fn = self._create_callable()

    def _create_callable(self) -> Callable:
        async def tool_func(query: str):
            return await self.agent.run(query, context={})

        tool_func.__name__ = self.agent.name
        tool_func.__doc__ = self.description
        return tool_func

    def to_gemini_tool(self):
        return self.fn
