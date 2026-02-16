"""
Mirascope Trading Client - Unified LLM Interface for Trading System.

Mirascope provides composable primitives for LLMs:
- Streaming for real-time updates
- Tool calling for trading functions
- Structured outputs via Pydantic models
- Unified interface across Anthropic, OpenAI, Gemini

This client wraps Mirascope to provide:
1. Provider hot-swapping (Anthropic <-> OpenAI)
2. Streaming market analysis
3. Tool-augmented trading decisions
4. Type-safe structured outputs

Feb 2026 - Integrated with BATS model selection framework.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Iterator
from enum import Enum
from typing import Any, TypeVar

from pydantic import BaseModel, Field
from src.utils.llm_gateway import (
    OPENROUTER_BASE_URL,
    resolve_openai_compatible_config,
    resolve_openrouter_primary_and_fallback_configs,
)
from src.utils.model_selector import ModelSelector, get_model_selector
from src.utils.self_healing import get_anthropic_api_key
from src.utils.token_monitor import record_llm_usage
from src.utils.tool_definitions import ToolRegistry, get_default_registry

logger = logging.getLogger(__name__)

# Type variable for generic structured output
T = TypeVar("T", bound=BaseModel)


# =============================================================================
# PYDANTIC MODELS FOR STRUCTURED OUTPUTS
# =============================================================================


class TradeSignal(str, Enum):
    """Trading signal types."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    CLOSE = "CLOSE"


class RiskLevel(str, Enum):
    """Risk assessment levels."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class MarketRegime(str, Enum):
    """Market regime classifications."""

    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    SIDEWAYS = "SIDEWAYS"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"


class TradeDecision(BaseModel):
    """Structured output for trade decisions."""

    decision: TradeSignal = Field(description="The trading signal/decision")
    signal_strength: float = Field(ge=0.0, le=1.0, description="Signal confidence 0-1")
    confidence: float = Field(ge=0.0, le=1.0, description="Overall confidence in decision")
    reasoning: str = Field(description="Explanation of the decision")
    params: dict[str, Any] = Field(
        default_factory=dict, description="Trade parameters (strike, expiry, etc.)"
    )


class MarketAnalysis(BaseModel):
    """Structured output for market analysis."""

    sentiment: float = Field(ge=-1.0, le=1.0, description="Market sentiment -1 to 1")
    technicals: dict[str, float] = Field(default_factory=dict, description="Technical indicators")
    regime: MarketRegime = Field(description="Current market regime")
    key_levels: dict[str, float] = Field(
        default_factory=dict, description="Support/resistance levels"
    )
    summary: str = Field(description="Analysis summary")


class RiskAssessment(BaseModel):
    """Structured output for risk assessment."""

    risk_level: RiskLevel = Field(description="Overall risk level")
    max_loss: float = Field(ge=0.0, description="Maximum potential loss in dollars")
    probability_of_loss: float = Field(ge=0.0, le=1.0, description="Probability of loss")
    recommendation: str = Field(description="Risk management recommendation")
    mitigations: list[str] = Field(default_factory=list, description="Suggested risk mitigations")


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OPENROUTER = "openrouter"


# =============================================================================
# MIRASCOPE TRADING CLIENT
# =============================================================================


class MirascopeTradingClient:
    """
    Unified LLM interface using Mirascope primitives.

    Features:
    - Provider hot-swapping (Anthropic, OpenAI, OpenRouter)
    - Streaming for real-time analysis updates
    - Tool calling with trading functions
    - Type-safe structured outputs

    Usage:
        client = MirascopeTradingClient()

        # Streaming analysis
        for chunk in client.stream_analysis("Analyze SPY market conditions"):
            print(chunk, end="")

        # Structured output
        decision = client.structured_output(
            "Should I enter SPY iron condor?",
            TradeDecision
        )
        print(f"Decision: {decision.decision}, Confidence: {decision.confidence}")

        # Tool calling
        result = client.call_with_tools(
            "Calculate position size for SPY at $500",
            tools=["calculate_position_size"]
        )

        # Switch provider
        client.switch_provider(LLMProvider.OPENAI)
    """

    def __init__(
        self,
        provider: LLMProvider = LLMProvider.ANTHROPIC,
        model_selector: ModelSelector | None = None,
        tool_registry: ToolRegistry | None = None,
    ):
        self.provider = provider
        self.model_selector = model_selector or get_model_selector()
        self.tool_registry = tool_registry or get_default_registry()

        # Initialize clients lazily
        self._anthropic_client: Any = None
        self._openai_client: Any = None
        self._openrouter_primary_base_url: str | None = None
        self._openrouter_fallback_cfg: Any = None
        self._openrouter_fallback_client: Any = None

        logger.info(f"MirascopeTradingClient initialized with provider: {provider.value}")

    @property
    def anthropic_client(self) -> Any:
        """Lazy-load Anthropic client."""
        if self._anthropic_client is None:
            try:
                from anthropic import Anthropic

                self._anthropic_client = Anthropic(api_key=get_anthropic_api_key())
            except ImportError:
                raise ImportError("anthropic package not installed. Run: pip install anthropic")
        return self._anthropic_client

    @property
    def openai_client(self) -> Any:
        """Lazy-load OpenAI client (for OpenAI and OpenRouter)."""
        if self._openai_client is None:
            try:
                from openai import OpenAI

                if self.provider == LLMProvider.OPENROUTER:
                    primary_cfg, fallback_cfg = resolve_openrouter_primary_and_fallback_configs()
                    self._openrouter_primary_base_url = primary_cfg.base_url or OPENROUTER_BASE_URL
                    self._openrouter_fallback_cfg = fallback_cfg
                    cfg = primary_cfg
                else:
                    cfg = resolve_openai_compatible_config(
                        default_api_key_env="OPENAI_API_KEY",
                        default_base_url=None,
                    )

                self._openai_client = OpenAI(
                    api_key=cfg.api_key,
                    base_url=cfg.base_url,
                )
            except ImportError:
                raise ImportError("openai package not installed. Run: pip install openai")
        return self._openai_client

    def _openai_chat_completions_create(self, **kwargs: Any) -> Any:
        """
        Wrapper around OpenAI-compatible `chat.completions.create` with optional
        gateway (TARS) model-id translation and OpenRouter-direct retry.
        """
        if self.provider != LLMProvider.OPENROUTER:
            return self.openai_client.chat.completions.create(**kwargs)

        from src.utils.model_selector import to_tars_model_id

        # Ensure openai_client is initialized and primary/fallback are populated.
        _ = self.openai_client

        model = str(kwargs.get("model") or "")
        using_gateway = bool(self._openrouter_primary_base_url) and (
            self._openrouter_primary_base_url.rstrip("/") != OPENROUTER_BASE_URL.rstrip("/")
        )
        if using_gateway:
            kwargs = dict(kwargs)
            kwargs["model"] = to_tars_model_id(model)

        try:
            return self.openai_client.chat.completions.create(**kwargs)
        except Exception as gateway_exc:
            if not self._openrouter_fallback_cfg:
                raise

            logger.warning(
                "OpenRouter gateway call failed (%s). Retrying via OpenRouter direct.",
                gateway_exc,
            )
            if self._openrouter_fallback_client is None:
                from openai import OpenAI

                self._openrouter_fallback_client = OpenAI(
                    api_key=self._openrouter_fallback_cfg.api_key,
                    base_url=self._openrouter_fallback_cfg.base_url,
                )
            fallback_kwargs = dict(kwargs)
            fallback_kwargs["model"] = model  # canonical OpenRouter ID
            return self._openrouter_fallback_client.chat.completions.create(**fallback_kwargs)

    def switch_provider(self, provider: LLMProvider) -> None:
        """
        Hot-swap between LLM providers.

        Args:
            provider: New provider to switch to
        """
        self.provider = provider
        # Reset OpenAI client since it may need different config
        self._openai_client = None
        logger.info(f"Switched to provider: {provider.value}")

    def _get_model(self, task_type: str = "technical_analysis") -> str:
        """Get appropriate model for task using BATS framework."""
        return self.model_selector.select_model(task_type)

    def _record_usage(self, model: str, input_tokens: int, output_tokens: int) -> None:
        """Record token usage for monitoring."""
        record_llm_usage(
            agent_name="mirascope_client",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=model,
        )
        self.model_selector.log_usage(model, input_tokens, output_tokens)

    # =========================================================================
    # STREAMING METHODS
    # =========================================================================

    def stream_analysis(
        self,
        prompt: str,
        task_type: str = "technical_analysis",
    ) -> Iterator[str]:
        """
        Stream market analysis for real-time updates.

        Args:
            prompt: Analysis prompt
            task_type: Task type for model selection

        Yields:
            Text chunks as they are generated
        """
        model = self._get_model(task_type)
        system_prompt = (
            "You are a quantitative trading analyst specializing in SPY iron condors. "
            "Provide concise, actionable analysis."
        )

        if self.provider == LLMProvider.ANTHROPIC:
            yield from self._stream_anthropic(prompt, model, system_prompt)
        else:
            yield from self._stream_openai(prompt, model, system_prompt)

    def _stream_anthropic(self, prompt: str, model: str, system_prompt: str) -> Iterator[str]:
        """Stream using Anthropic API."""
        total_input = 0
        total_output = 0

        with self.anthropic_client.messages.stream(
            model=model,
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for text in stream.text_stream:
                total_output += len(text) // 4  # Rough token estimate
                yield text

        # Estimate input tokens (rough)
        total_input = len(prompt) // 4 + len(system_prompt) // 4
        self._record_usage(model, total_input, total_output)

    def _stream_openai(self, prompt: str, model: str, system_prompt: str) -> Iterator[str]:
        """Stream using OpenAI-compatible API."""
        total_output = 0

        # Map Anthropic models to OpenAI/OpenRouter equivalents
        if "claude" in model.lower():
            if self.provider == LLMProvider.OPENROUTER:
                model = "anthropic/claude-3-opus"  # Via OpenRouter
            else:
                model = "gpt-4o"  # Fallback

        stream = self._openai_chat_completions_create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            max_tokens=2048,
            stream=True,
        )

        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                text = chunk.choices[0].delta.content
                total_output += len(text) // 4
                yield text

        total_input = len(prompt) // 4 + len(system_prompt) // 4
        self._record_usage(model, total_input, total_output)

    async def stream_analysis_async(
        self,
        prompt: str,
        task_type: str = "technical_analysis",
    ) -> AsyncIterator[str]:
        """
        Async streaming for market analysis.

        Args:
            prompt: Analysis prompt
            task_type: Task type for model selection

        Yields:
            Text chunks as they are generated
        """
        model = self._get_model(task_type)
        system_prompt = (
            "You are a quantitative trading analyst specializing in SPY iron condors. "
            "Provide concise, actionable analysis."
        )

        if self.provider == LLMProvider.ANTHROPIC:
            async for chunk in self._stream_anthropic_async(prompt, model, system_prompt):
                yield chunk
        else:
            async for chunk in self._stream_openai_async(prompt, model, system_prompt):
                yield chunk

    async def _stream_anthropic_async(
        self, prompt: str, model: str, system_prompt: str
    ) -> AsyncIterator[str]:
        """Async stream using Anthropic API."""
        try:
            from anthropic import AsyncAnthropic

            client = AsyncAnthropic(api_key=get_anthropic_api_key())
            total_output = 0

            async with client.messages.stream(
                model=model,
                max_tokens=2048,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                async for text in stream.text_stream:
                    total_output += len(text) // 4
                    yield text

            total_input = len(prompt) // 4 + len(system_prompt) // 4
            self._record_usage(model, total_input, total_output)
        except ImportError:
            yield "Error: anthropic async not available"

    async def _stream_openai_async(
        self, prompt: str, model: str, system_prompt: str
    ) -> AsyncIterator[str]:
        """Async stream using OpenAI-compatible API."""
        try:
            from openai import AsyncOpenAI

            if self.provider == LLMProvider.OPENROUTER:
                primary_cfg, fallback_cfg = resolve_openrouter_primary_and_fallback_configs()
                cfg = primary_cfg
            else:
                fallback_cfg = None
                cfg = resolve_openai_compatible_config(
                    default_api_key_env="OPENAI_API_KEY",
                    default_base_url=None,
                )

            client = AsyncOpenAI(api_key=cfg.api_key, base_url=cfg.base_url)

            if "claude" in model.lower():
                model = (
                    "anthropic/claude-3-opus"
                    if self.provider == LLMProvider.OPENROUTER
                    else "gpt-4o"
                )

            from src.utils.model_selector import to_tars_model_id

            using_gateway = bool(cfg.base_url) and (
                str(cfg.base_url).rstrip("/") != OPENROUTER_BASE_URL.rstrip("/")
            )
            model_for_call = to_tars_model_id(model) if using_gateway else model

            total_output = 0
            try:
                stream = await client.chat.completions.create(
                    model=model_for_call,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=2048,
                    stream=True,
                )
            except Exception as gateway_exc:
                if fallback_cfg:
                    logger.warning(
                        "OpenRouter gateway async call failed (%s). Retrying via OpenRouter direct.",
                        gateway_exc,
                    )
                    fallback_client = AsyncOpenAI(
                        api_key=fallback_cfg.api_key, base_url=fallback_cfg.base_url
                    )
                    stream = await fallback_client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt},
                        ],
                        max_tokens=2048,
                        stream=True,
                    )
                else:
                    raise

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    text = chunk.choices[0].delta.content
                    total_output += len(text) // 4
                    yield text

            total_input = len(prompt) // 4 + len(system_prompt) // 4
            self._record_usage(model, total_input, total_output)
        except ImportError:
            yield "Error: openai async not available"

    # =========================================================================
    # TOOL CALLING METHODS
    # =========================================================================

    def call_with_tools(
        self,
        prompt: str,
        tools: list[str] | None = None,
        task_type: str = "technical_analysis",
    ) -> dict[str, Any]:
        """
        Execute prompt with trading tool access.

        Args:
            prompt: User prompt
            tools: List of tool names to enable (None = all trading tools)
            task_type: Task type for model selection

        Returns:
            Dict with response and any tool calls
        """
        model = self._get_model(task_type)

        # Get tool definitions
        tool_defs = (
            self.tool_registry.to_claude(tools)
            if self.provider == LLMProvider.ANTHROPIC
            else self.tool_registry.to_openrouter(tools)
        )

        if self.provider == LLMProvider.ANTHROPIC:
            return self._call_tools_anthropic(prompt, model, tool_defs)
        else:
            return self._call_tools_openai(prompt, model, tool_defs)

    def _call_tools_anthropic(self, prompt: str, model: str, tools: list[dict]) -> dict[str, Any]:
        """Tool calling via Anthropic API."""
        response = self.anthropic_client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
            tools=tools,
        )

        # Record usage
        if response.usage:
            self._record_usage(model, response.usage.input_tokens, response.usage.output_tokens)

        # Parse response
        result: dict[str, Any] = {
            "text": "",
            "tool_calls": [],
            "stop_reason": response.stop_reason,
        }

        for block in response.content:
            if block.type == "text":
                result["text"] = block.text
            elif block.type == "tool_use":
                result["tool_calls"].append(
                    {
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                )

        return result

    def _call_tools_openai(self, prompt: str, model: str, tools: list[dict]) -> dict[str, Any]:
        """Tool calling via OpenAI-compatible API."""
        if "claude" in model.lower():
            model = (
                "anthropic/claude-3-opus" if self.provider == LLMProvider.OPENROUTER else "gpt-4o"
            )

        response = self._openai_chat_completions_create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            tools=tools,
            max_tokens=4096,
        )

        # Record usage
        if response.usage:
            self._record_usage(
                model, response.usage.prompt_tokens, response.usage.completion_tokens
            )

        # Parse response
        result: dict[str, Any] = {
            "text": "",
            "tool_calls": [],
            "stop_reason": (response.choices[0].finish_reason if response.choices else None),
        }

        if response.choices:
            choice = response.choices[0]
            if choice.message.content:
                result["text"] = choice.message.content
            if choice.message.tool_calls:
                for tc in choice.message.tool_calls:
                    result["tool_calls"].append(
                        {
                            "id": tc.id,
                            "name": tc.function.name,
                            "input": tc.function.arguments,
                        }
                    )

        return result

    # =========================================================================
    # STRUCTURED OUTPUT METHODS
    # =========================================================================

    def structured_output(
        self,
        prompt: str,
        output_model: type[T],
        task_type: str = "technical_analysis",
    ) -> T:
        """
        Get structured output as a Pydantic model.

        Args:
            prompt: User prompt
            output_model: Pydantic model class for output
            task_type: Task type for model selection

        Returns:
            Instance of output_model with parsed response
        """
        model = self._get_model(task_type)

        # Build schema-aware system prompt
        schema = output_model.model_json_schema()
        system_prompt = f"""You are a trading analysis assistant.
Respond with valid JSON matching this schema:
{schema}

Only output valid JSON, no additional text."""

        if self.provider == LLMProvider.ANTHROPIC:
            return self._structured_anthropic(prompt, model, output_model, system_prompt)
        else:
            return self._structured_openai(prompt, model, output_model, system_prompt)

    def _structured_anthropic(
        self,
        prompt: str,
        model: str,
        output_model: type[T],
        system_prompt: str,
    ) -> T:
        """Structured output via Anthropic API."""
        response = self.anthropic_client.messages.create(
            model=model,
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )

        if response.usage:
            self._record_usage(model, response.usage.input_tokens, response.usage.output_tokens)

        # Extract and parse JSON
        text = ""
        for block in response.content:
            if block.type == "text":
                text = block.text
                break

        return self._parse_json_output(text, output_model)

    def _structured_openai(
        self,
        prompt: str,
        model: str,
        output_model: type[T],
        system_prompt: str,
    ) -> T:
        """Structured output via OpenAI-compatible API."""
        if "claude" in model.lower():
            model = (
                "anthropic/claude-3-opus" if self.provider == LLMProvider.OPENROUTER else "gpt-4o"
            )

        response = self._openai_chat_completions_create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            max_tokens=2048,
            response_format={"type": "json_object"},
        )

        if response.usage:
            self._record_usage(
                model, response.usage.prompt_tokens, response.usage.completion_tokens
            )

        text = response.choices[0].message.content if response.choices else ""
        return self._parse_json_output(text or "", output_model)

    def _parse_json_output(self, text: str, output_model: type[T]) -> T:
        """Parse JSON text into Pydantic model."""
        import json

        # Try to extract JSON from response
        text = text.strip()

        # Handle markdown code blocks
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text

        try:
            data = json.loads(text)
            return output_model.model_validate(data)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}\nText: {text[:200]}")
            # Return default instance
            return output_model.model_construct()

    # =========================================================================
    # CONVENIENCE METHODS
    # =========================================================================

    def analyze_market(self, symbol: str = "SPY") -> MarketAnalysis:
        """Get structured market analysis for a symbol."""
        prompt = f"""Analyze current market conditions for {symbol}:
1. Overall sentiment (-1 bearish to +1 bullish)
2. Key technical indicators (RSI, MACD, etc.)
3. Current market regime
4. Key support/resistance levels
5. Brief summary"""

        return self.structured_output(prompt, MarketAnalysis, task_type="technical_analysis")

    def assess_risk(self, trade_params: dict[str, Any]) -> RiskAssessment:
        """Get structured risk assessment for a trade."""
        prompt = f"""Assess the risk for this trade:
{trade_params}

Consider:
1. Maximum potential loss
2. Probability of loss
3. Position size relative to account
4. Suggested mitigations"""

        return self.structured_output(prompt, RiskAssessment, task_type="risk_assessment")

    def get_trade_decision(self, context: str, strategy: str = "iron_condor") -> TradeDecision:
        """Get structured trade decision."""
        prompt = f"""Based on this context:
{context}

Should I enter a {strategy} trade on SPY?
Consider:
1. Signal direction and strength
2. Confidence level
3. Specific parameters (delta, DTE, width)
4. Clear reasoning"""

        return self.structured_output(prompt, TradeDecision, task_type="signal_generation")


# =============================================================================
# SINGLETON AND CONVENIENCE FUNCTIONS
# =============================================================================

_mirascope_client: MirascopeTradingClient | None = None


def get_mirascope_client(
    provider: LLMProvider = LLMProvider.ANTHROPIC,
) -> MirascopeTradingClient:
    """Get or create the global Mirascope client."""
    global _mirascope_client
    if _mirascope_client is None or _mirascope_client.provider != provider:
        _mirascope_client = MirascopeTradingClient(provider=provider)
    return _mirascope_client


def stream_analysis(prompt: str) -> Iterator[str]:
    """Convenience function for streaming analysis."""
    return get_mirascope_client().stream_analysis(prompt)


def get_trade_decision(context: str) -> TradeDecision:
    """Convenience function for trade decisions."""
    return get_mirascope_client().get_trade_decision(context)


def analyze_market(symbol: str = "SPY") -> MarketAnalysis:
    """Convenience function for market analysis."""
    return get_mirascope_client().analyze_market(symbol)
