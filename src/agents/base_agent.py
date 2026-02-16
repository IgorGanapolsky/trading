"""
Base Agent Class - Foundation for all trading agents

Updated December 2025: Integrated BATS (Budget-Aware Test-time Scaling)
for intelligent model selection based on task complexity and budget.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from anthropic import Anthropic
from src.orchestration.context_engine import (
    ContextMemory,
    MemoryTimescale,
    get_context_engine,
)
from src.utils.llm_gateway import (
    OPENROUTER_BASE_URL,
    resolve_openrouter_primary_and_fallback_configs,
)
from src.utils.model_selector import get_model_selector
from src.utils.self_healing import get_anthropic_api_key, with_retry
from src.utils.token_monitor import record_llm_usage

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Base class for all trading agents.

    Each agent has:
    - LLM reasoning capability (Claude)
    - Tool orchestration (can call external APIs)
    - Memory (learns from past decisions)
    - Transparency (auditable decision logs)

    December 2025 Update:
    - Integrated BATS framework for budget-aware model selection
    - Model selection based on agent name and task complexity
    - CRITICAL tasks (trade execution) always use Opus
    - Pass model=None to use automatic selection
    """

    def __init__(
        self,
        name: str,
        role: str,
        model: str | None = None,  # None = use ModelSelector
        use_context_engine: bool = True,
    ):
        self.name = name
        self.role = role

        # BATS Framework: Select model based on agent name if not explicitly provided
        # This ensures budget-aware model selection while maintaining backward compatibility
        model_selector = get_model_selector()
        if model is None:
            self.model = model_selector.get_model_for_agent(name)
            logger.info(f"{name}: Auto-selected model {self.model} via BATS framework")
        else:
            self.model = model
            logger.info(f"{name}: Using explicitly provided model {self.model}")

        # Route to correct provider based on model selection
        self._provider = model_selector.get_model_provider(self.model)

        # OpenRouter is an OpenAI-compatible provider. If a gateway (e.g. TARS) is configured
        # via `LLM_GATEWAY_BASE_URL`, we'll route through it and optionally retry via
        # OpenRouter direct when the gateway is unavailable.
        self._openrouter_primary_base_url = None
        self._openrouter_fallback_cfg = None
        self._openrouter_fallback_client = None

        if self._provider == "openrouter":
            try:
                from openai import OpenAI

                primary_cfg, fallback_cfg = resolve_openrouter_primary_and_fallback_configs()
                self._openrouter_primary_base_url = primary_cfg.base_url or OPENROUTER_BASE_URL
                self._openrouter_fallback_cfg = fallback_cfg

                self._openrouter_client = OpenAI(
                    api_key=primary_cfg.api_key,
                    base_url=self._openrouter_primary_base_url,
                )
                self.client = None  # Not using Anthropic for this agent
                logger.info(f"{name}: Using OpenRouter provider for model {self.model}")
            except ImportError:
                logger.warning(f"{name}: openai package unavailable, falling back to Anthropic")
                self._provider = "anthropic"
                self._openrouter_client = None
                self.client = Anthropic(api_key=get_anthropic_api_key())
        else:
            self._openrouter_client = None
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
    def reason_with_llm(self, prompt: str, tools: list[dict] | None = None) -> dict[str, Any]:
        """
        Use LLM reasoning to make decisions.

        Routes to OpenRouter or Anthropic based on model provider selection.

        Args:
            prompt: The reasoning prompt
            tools: Optional tool definitions for tool use

        Returns:
            LLM response with reasoning
        """
        if self._provider == "openrouter" and self._openrouter_client is not None:
            return self._reason_with_openrouter(prompt, tools)
        return self._reason_with_anthropic(prompt, tools)

    def _reason_with_anthropic(
        self, prompt: str, tools: list[dict] | None = None
    ) -> dict[str, Any]:
        """Reason using Anthropic API (Claude models)."""
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

            # Record token usage for monitoring
            if hasattr(response, "usage") and response.usage:
                alerts = record_llm_usage(
                    agent_name=self.name,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    model=self.model,
                )
                if alerts:
                    logger.warning(f"{self.name} token alerts: {alerts}")

            # Extract text content
            result = {
                "reasoning": "",
                "decision": "",
                "confidence": 0.0,
                "tool_calls": [],
                "token_usage": {
                    "input": response.usage.input_tokens if response.usage else 0,
                    "output": response.usage.output_tokens if response.usage else 0,
                },
            }

            for block in response.content:
                if block.type == "text":
                    result["reasoning"] = block.text
                elif block.type == "tool_use":
                    result["tool_calls"].append({"name": block.name, "input": block.input})

            return result

        except Exception as e:
            logger.error(f"{self.name} LLM reasoning error (Anthropic): {e}")
            return {
                "reasoning": f"Error: {str(e)}",
                "decision": "NO_ACTION",
                "confidence": 0.0,
                "tool_calls": [],
                "token_usage": {"input": 0, "output": 0},
            }

    def _reason_with_openrouter(
        self, prompt: str, tools: list[dict] | None = None
    ) -> dict[str, Any]:
        """Reason using OpenRouter API (DeepSeek, Mistral, Kimi K2)."""
        try:
            from src.utils.model_selector import to_tars_model_id

            messages = [{"role": "user", "content": prompt}]

            using_gateway = bool(self._openrouter_primary_base_url) and (
                self._openrouter_primary_base_url.rstrip("/") != OPENROUTER_BASE_URL.rstrip("/")
            )
            model_for_call = to_tars_model_id(self.model) if using_gateway else self.model

            kwargs: dict[str, Any] = {
                "model": model_for_call,
                "max_tokens": 4096,
                "messages": messages,
            }
            if tools:
                # Convert Anthropic tool format to OpenAI format if needed
                openai_tools = []
                for tool in tools:
                    if "function" in tool:
                        openai_tools.append(tool)
                    elif "name" in tool and "input_schema" in tool:
                        openai_tools.append(
                            {
                                "type": "function",
                                "function": {
                                    "name": tool["name"],
                                    "description": tool.get("description", ""),
                                    "parameters": tool["input_schema"],
                                },
                            }
                        )
                if openai_tools:
                    kwargs["tools"] = openai_tools

            try:
                response = self._openrouter_client.chat.completions.create(**kwargs)
            except Exception as gateway_exc:
                # If we're using a gateway (TARS) and it's down, retry via OpenRouter direct
                # if OPENROUTER_API_KEY is configured.
                if self._openrouter_fallback_cfg:
                    logger.warning(
                        "%s: gateway call failed (%s). Retrying via OpenRouter direct.",
                        self.name,
                        gateway_exc,
                    )
                    if self._openrouter_fallback_client is None:
                        from openai import OpenAI

                        self._openrouter_fallback_client = OpenAI(
                            api_key=self._openrouter_fallback_cfg.api_key,
                            base_url=self._openrouter_fallback_cfg.base_url,
                        )
                    fallback_kwargs = dict(kwargs)
                    fallback_kwargs["model"] = self.model  # canonical OpenRouter ID
                    response = self._openrouter_fallback_client.chat.completions.create(
                        **fallback_kwargs
                    )
                else:
                    raise

            # Record token usage
            input_tokens = response.usage.prompt_tokens if response.usage else 0
            output_tokens = response.usage.completion_tokens if response.usage else 0

            if input_tokens or output_tokens:
                alerts = record_llm_usage(
                    agent_name=self.name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    model=self.model,
                )
                if alerts:
                    logger.warning(f"{self.name} token alerts: {alerts}")

            # Extract text content
            text = ""
            tool_calls = []
            if response.choices:
                choice = response.choices[0]
                text = choice.message.content or ""
                if choice.message.tool_calls:
                    for tc in choice.message.tool_calls:
                        tool_calls.append(
                            {
                                "name": tc.function.name,
                                "input": tc.function.arguments,
                            }
                        )

            return {
                "reasoning": text,
                "decision": "",
                "confidence": 0.0,
                "tool_calls": tool_calls,
                "token_usage": {
                    "input": input_tokens,
                    "output": output_tokens,
                },
            }

        except Exception as e:
            logger.error(f"{self.name} LLM reasoning error (OpenRouter): {e}")
            return {
                "reasoning": f"Error: {str(e)}",
                "decision": "NO_ACTION",
                "confidence": 0.0,
                "tool_calls": [],
                "token_usage": {"input": 0, "output": 0},
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
        timescale: MemoryTimescale | None = None,
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
        use_multi_timescale: bool | None = None,
        timescales: list[MemoryTimescale] | None = None,
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
