"""
Base Agent Class - Foundation for all trading agents
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

from anthropic import Anthropic

from src.agent_framework.context_engine import (
    ContextMemory,
    MemoryTimescale,
    get_context_engine,
)
from src.utils.self_healing import get_anthropic_api_key, with_retry

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Base class for all trading agents.

    Each agent has:
    - LLM reasoning capability (Claude)
    - Tool orchestration (can call external APIs)
    - Memory (learns from past decisions)
    - Transparency (auditable decision logs)
    """

    def __init__(
        self,
        name: str,
        role: str,
        model: str = "claude-3-opus-20240229",
        use_context_engine: bool = True,
    ):
        self.name = name
        self.role = role
        self.model = model
        self.client = Anthropic(api_key=get_anthropic_api_key())
        self.memory: list[dict[str, Any]] = []  # Legacy memory (backward compatibility)
        self.decision_log: list[dict[str, Any]] = []
        self.use_context_engine = use_context_engine
        self.context_engine = get_context_engine() if use_context_engine else None

    @abstractmethod
    def analyze(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Main analysis method - must be implemented by each agent.

        Args:
            data: Input data for analysis

        Returns:
            Analysis results with reasoning
        """
        pass

    @with_retry(max_attempts=3, backoff=2.0)
    def reason_with_llm(self, prompt: str, tools: Optional[list[dict]] = None) -> dict[str, Any]:
        """
        Use LLM reasoning to make decisions.

        Args:
            prompt: The reasoning prompt
            tools: Optional tool definitions for tool use

        Returns:
            LLM response with reasoning
        """
        try:
            messages = [{"role": "user", "content": prompt}]

            if tools:
                response = self.client.messages.create(
                    model=self.model, max_tokens=4096, messages=messages, tools=tools
                )
            else:
                response = self.client.messages.create(
                    model=self.model, max_tokens=4096, messages=messages
                )

            # Extract text content
            result = {
                "reasoning": "",
                "decision": "",
                "confidence": 0.0,
                "tool_calls": [],
            }

            for block in response.content:
                if block.type == "text":
                    result["reasoning"] = block.text
                elif block.type == "tool_use":
                    result["tool_calls"].append({"name": block.name, "input": block.input})

            return result

        except Exception as e:
            logger.error(f"{self.name} LLM reasoning error: {e}")
            return {
                "reasoning": f"Error: {str(e)}",
                "decision": "NO_ACTION",
                "confidence": 0.0,
                "tool_calls": [],
            }

    def log_decision(self, decision: dict[str, Any]) -> None:
        """Log a decision for audit trail and learning."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": self.name,
            "decision": decision,
        }
        self.decision_log.append(entry)
        logger.info(f"{self.name} decision logged: {decision.get('action', 'N/A')}")

    def learn_from_outcome(
        self,
        decision_id: str,
        outcome: dict[str, Any],
        timescale: Optional[MemoryTimescale] = None,
    ) -> None:
        """
        Learn from decision outcomes (reinforcement learning).

        Enhanced with multi-timescale memory support for nested learning.

        Args:
            decision_id: ID of the decision
            outcome: Result data (profit/loss, accuracy, etc.)
            timescale: Memory timescale (None = auto-determine)
        """
        memory_entry = {
            "decision_id": decision_id,
            "outcome": outcome,
            "timestamp": datetime.now().isoformat(),
        }

        # Store in legacy memory (backward compatibility)
        self.memory.append(memory_entry)

        # Store in ContextEngine multi-timescale memory
        if self.context_engine:
            pl = outcome.get("pl", 0.0)
            tags = {self.name, "outcome", outcome.get("result", "unknown")}

            # Determine timescale from outcome type
            if timescale is None:
                if outcome.get("result") == "WIN" and abs(pl) > 50:
                    timescale = MemoryTimescale.EPISODIC  # Important wins
                elif outcome.get("result") == "LOSS" and abs(pl) > 50:
                    timescale = MemoryTimescale.EPISODIC  # Important losses
                else:
                    timescale = MemoryTimescale.DAILY  # Default

            self.context_engine.store_memory(
                agent_id=self.name,
                content=memory_entry,
                tags=tags,
                timescale=timescale,
                outcome_pl=pl,
            )

        logger.info(
            f"{self.name} learned from outcome: {outcome.get('result', 'N/A')} [timescale: {timescale.value if timescale else 'legacy'}]"
        )

    def get_memory_context(
        self,
        limit: int = 10,
        use_multi_timescale: Optional[bool] = None,
        timescales: Optional[list[MemoryTimescale]] = None,
    ) -> str:
        """
        Get memory context for LLM reasoning.

        Enhanced with multi-timescale memory support for nested learning.

        Args:
            limit: Number of memories to include
            use_multi_timescale: Use multi-timescale memory (None = auto)
            timescales: Specific timescales to retrieve (multi-timescale only)

        Returns:
            Formatted memory context string
        """
        # Use ContextEngine multi-timescale memory if available
        if self.context_engine and (use_multi_timescale is not False):
            memories = self.context_engine.retrieve_memories(
                agent_id=self.name,
                limit=limit,
                timescales=timescales,
                use_multi_timescale=True,
            )

            if memories:
                context = "Multi-timescale experience:\n"

                # Group by timescale
                timescale_groups: dict[str, list[ContextMemory]] = {}
                for mem in memories:
                    ts = mem.timescale.value
                    if ts not in timescale_groups:
                        timescale_groups[ts] = []
                    timescale_groups[ts].append(mem)

                # Format by timescale
                for timescale_name in [
                    "episodic",
                    "monthly",
                    "weekly",
                    "daily",
                    "intraday",
                ]:
                    if timescale_name in timescale_groups:
                        context += f"\n{timescale_name.upper()} patterns:\n"
                        for mem in timescale_groups[timescale_name]:
                            content = mem.content
                            outcome = content.get("outcome", {})
                            pl = mem.outcome_pl or outcome.get("pl", 0.0)
                            importance = mem.importance_score
                            context += (
                                f"- {content.get('timestamp', 'N/A')}: "
                                f"{outcome.get('result', 'N/A')} "
                                f"(P/L: ${pl:.2f}, importance: {importance:.2f})\n"
                            )

                return context

        # Fallback to legacy memory
        recent_memories = self.memory[-limit:]
        if not recent_memories:
            return "No previous experience."

        context = "Recent experience:\n"
        for mem in recent_memories:
            outcome = mem.get("outcome", {})
            context += f"- {mem['timestamp']}: {outcome.get('result', 'N/A')} "
            context += f"(P/L: {outcome.get('pl', 0):.2f})\n"

        return context
