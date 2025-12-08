"""
Local LLM Inference Support for OpenThinker-Agent and other local models.

Supports:
- vLLM (OpenAI-compatible API)
- Ollama (local inference)
- Hugging Face Transformers (direct inference)

This module enables cost-free reasoning with open-source models like OpenThinker.
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class LocalLLMBackend(Enum):
    """Supported local LLM backends."""

    VLLM = "vllm"  # vLLM OpenAI-compatible server
    OLLAMA = "ollama"  # Ollama local inference
    OPENAI_COMPATIBLE = "openai_compatible"  # Any OpenAI-compatible endpoint


class LocalModel(Enum):
    """Available local models for trading analysis."""

    # OpenThinker family - reasoning-focused models
    OPENTHINKER_7B = "openthinker:7b"
    OPENTHINKER_32B = "openthinker:32b"
    OPENTHINKER3_7B = "open-thoughts/OpenThinker3-7B"

    # OpenThinker-Agent - agentic reasoning model
    OPENTHINKER_AGENT_V1 = "open-thoughts/OpenThinker-Agent-v1"

    # Qwen reasoning models (base for OpenThinker)
    QWEN_7B = "qwen2.5:7b-instruct"
    QWEN_32B = "qwen2.5:32b-instruct"


@dataclass
class LocalLLMResponse:
    """Container for local LLM response data."""

    model: str
    content: str
    tokens_used: int
    latency: float
    success: bool
    error: str | None = None
    thinking: str | None = None  # For reasoning models that output thinking


class LocalLLMClient:
    """
    Client for local LLM inference supporting multiple backends.

    Supports vLLM, Ollama, and any OpenAI-compatible endpoint.
    Optimized for reasoning models like OpenThinker that benefit from
    extended thinking time.
    """

    def __init__(
        self,
        backend: LocalLLMBackend = LocalLLMBackend.OLLAMA,
        base_url: str | None = None,
        model: LocalModel | str = LocalModel.OPENTHINKER_7B,
        timeout: int = 120,  # Longer timeout for reasoning models
    ):
        """
        Initialize Local LLM Client.

        Args:
            backend: LLM backend to use (vllm, ollama, openai_compatible)
            base_url: Base URL for the API (auto-detected if not provided)
            model: Model to use for inference
            timeout: Request timeout in seconds (higher for reasoning models)
        """
        self.backend = backend
        self.model = model.value if isinstance(model, LocalModel) else model
        self.timeout = timeout

        # Auto-detect base URL based on backend
        if base_url:
            self.base_url = base_url
        elif backend == LocalLLMBackend.OLLAMA:
            self.base_url = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        elif backend == LocalLLMBackend.VLLM:
            self.base_url = os.getenv("VLLM_HOST", "http://localhost:8000")
        else:
            self.base_url = os.getenv("LOCAL_LLM_HOST", "http://localhost:8000")

        self.client = httpx.AsyncClient(timeout=timeout)

        logger.info(
            f"Initialized LocalLLMClient: backend={backend.value}, "
            f"model={self.model}, base_url={self.base_url}"
        )

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        enable_thinking: bool = True,
    ) -> LocalLLMResponse:
        """
        Generate response from local LLM.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            enable_thinking: Enable extended thinking for reasoning models

        Returns:
            LocalLLMResponse with generation results
        """
        start_time = time.time()

        try:
            if self.backend == LocalLLMBackend.OLLAMA:
                result = await self._generate_ollama(
                    prompt, system_prompt, temperature, max_tokens
                )
            else:
                result = await self._generate_openai_compatible(
                    prompt, system_prompt, temperature, max_tokens
                )

            latency = time.time() - start_time
            result.latency = latency

            logger.debug(
                f"Local LLM generated in {latency:.2f}s: "
                f"{len(result.content)} chars, {result.tokens_used} tokens"
            )

            return result

        except Exception as e:
            latency = time.time() - start_time
            logger.error(f"Local LLM generation error: {e}")
            return LocalLLMResponse(
                model=self.model,
                content="",
                tokens_used=0,
                latency=latency,
                success=False,
                error=str(e),
            )

    async def _generate_ollama(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
        max_tokens: int,
    ) -> LocalLLMResponse:
        """Generate using Ollama API."""
        url = f"{self.base_url}/api/generate"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        if system_prompt:
            payload["system"] = system_prompt

        response = await self.client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

        content = data.get("response", "")
        thinking = None

        # Extract thinking from reasoning models (OpenThinker format)
        if "<think>" in content and "</think>" in content:
            think_start = content.index("<think>") + len("<think>")
            think_end = content.index("</think>")
            thinking = content[think_start:think_end].strip()
            # Remove thinking from main content
            content = content[think_end + len("</think>") :].strip()

        return LocalLLMResponse(
            model=self.model,
            content=content,
            tokens_used=data.get("eval_count", 0) + data.get("prompt_eval_count", 0),
            latency=0,  # Will be set by caller
            success=True,
            thinking=thinking,
        )

    async def _generate_openai_compatible(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
        max_tokens: int,
    ) -> LocalLLMResponse:
        """Generate using OpenAI-compatible API (vLLM, etc.)."""
        url = f"{self.base_url}/v1/chat/completions"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        response = await self.client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

        content = data["choices"][0]["message"]["content"]
        thinking = None

        # Extract thinking from reasoning models
        if "<think>" in content and "</think>" in content:
            think_start = content.index("<think>") + len("<think>")
            think_end = content.index("</think>")
            thinking = content[think_start:think_end].strip()
            content = content[think_end + len("</think>") :].strip()

        usage = data.get("usage", {})

        return LocalLLMResponse(
            model=self.model,
            content=content,
            tokens_used=usage.get("total_tokens", 0),
            latency=0,
            success=True,
            thinking=thinking,
        )

    async def is_available(self) -> bool:
        """Check if the local LLM backend is available."""
        try:
            if self.backend == LocalLLMBackend.OLLAMA:
                url = f"{self.base_url}/api/tags"
            else:
                url = f"{self.base_url}/v1/models"

            response = await self.client.get(url, timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        """List available models on the local backend."""
        try:
            if self.backend == LocalLLMBackend.OLLAMA:
                url = f"{self.base_url}/api/tags"
                response = await self.client.get(url)
                response.raise_for_status()
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
            else:
                url = f"{self.base_url}/v1/models"
                response = await self.client.get(url)
                response.raise_for_status()
                data = response.json()
                return [m["id"] for m in data.get("data", [])]
        except Exception as e:
            logger.warning(f"Failed to list models: {e}")
            return []

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


class OpenThinkerReasoner:
    """
    OpenThinker reasoning specialist for trading analysis.

    Uses OpenThinker models for deep reasoning on complex trading decisions.
    Optimized for:
    - Multi-step reasoning problems
    - Mathematical analysis (position sizing, risk calculations)
    - Complex decision trees (trade evaluation)
    """

    def __init__(
        self,
        model: LocalModel = LocalModel.OPENTHINKER_7B,
        backend: LocalLLMBackend = LocalLLMBackend.OLLAMA,
        base_url: str | None = None,
    ):
        """
        Initialize OpenThinker Reasoner.

        Args:
            model: OpenThinker model variant to use
            backend: Local LLM backend (ollama, vllm)
            base_url: Optional custom base URL
        """
        self.client = LocalLLMClient(
            backend=backend,
            base_url=base_url,
            model=model,
            timeout=180,  # Extended timeout for reasoning
        )
        self.model = model

        logger.info(f"Initialized OpenThinkerReasoner with model={model.value}")

    async def reason(
        self,
        query: str,
        context: dict[str, Any] | None = None,
        require_confidence: bool = True,
    ) -> dict[str, Any]:
        """
        Perform deep reasoning on a trading question.

        Args:
            query: The trading question to reason about
            context: Additional context (market data, positions, etc.)
            require_confidence: Whether to require confidence score

        Returns:
            Dictionary with reasoning results, decision, and confidence
        """
        system_prompt = """You are an expert trading analyst with deep reasoning capabilities.

<role>
You excel at complex multi-step analysis of trading decisions.
Think through problems step-by-step before reaching conclusions.
</role>

<reasoning_protocol>
1. First, understand the question fully
2. Break down the problem into components
3. Analyze each component systematically
4. Consider risks and edge cases
5. Synthesize into a clear recommendation
</reasoning_protocol>

<output_format>
Provide your analysis with:
- REASONING: Step-by-step thought process
- DECISION: Clear recommendation (BUY/SELL/HOLD)
- CONFIDENCE: Score from 0.0 to 1.0
- KEY_FACTORS: List of decisive factors
- RISKS: Potential risks or concerns
</output_format>"""

        # Build prompt with context
        prompt = query
        if context:
            prompt = f"""Context:
{_format_context(context)}

Query: {query}

Analyze thoroughly and provide your recommendation."""

        response = await self.client.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3,  # Lower temp for more consistent reasoning
            max_tokens=4096,
            enable_thinking=True,
        )

        if not response.success:
            return {
                "success": False,
                "error": response.error,
                "reasoning": "",
                "decision": "HOLD",
                "confidence": 0.0,
            }

        # Parse the response
        result = self._parse_reasoning_response(response)
        result["thinking"] = response.thinking
        result["latency"] = response.latency
        result["model"] = response.model

        return result

    async def analyze_trade(
        self,
        symbol: str,
        action: str,
        market_data: dict[str, Any],
        portfolio_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Analyze a specific trade proposal using deep reasoning.

        Args:
            symbol: Stock symbol
            action: Proposed action (BUY/SELL)
            market_data: Current market data
            portfolio_context: Portfolio context

        Returns:
            Detailed trade analysis with recommendation
        """
        query = f"""Should we {action} {symbol}?

Market Data:
- Current Price: ${market_data.get('price', 'N/A')}
- Change: {market_data.get('change_pct', 0):.2f}%
- RSI: {market_data.get('rsi', 'N/A')}
- MACD Signal: {market_data.get('macd_signal', 'N/A')}
- Volume: {market_data.get('volume', 'N/A')}

Evaluate this trade proposal considering:
1. Technical indicators and momentum
2. Risk/reward ratio
3. Position sizing implications
4. Current market conditions"""

        context = {
            "symbol": symbol,
            "proposed_action": action,
            "market_data": market_data,
        }

        if portfolio_context:
            context["portfolio"] = portfolio_context

        return await self.reason(query, context)

    async def calculate_position_size(
        self,
        symbol: str,
        account_value: float,
        risk_per_trade: float,
        entry_price: float,
        stop_loss: float,
    ) -> dict[str, Any]:
        """
        Calculate optimal position size using mathematical reasoning.

        Args:
            symbol: Stock symbol
            account_value: Total account value
            risk_per_trade: Maximum risk per trade (as decimal, e.g., 0.02 for 2%)
            entry_price: Planned entry price
            stop_loss: Stop loss price

        Returns:
            Position sizing recommendation with reasoning
        """
        query = f"""Calculate the optimal position size for {symbol}.

Parameters:
- Account Value: ${account_value:,.2f}
- Risk per Trade: {risk_per_trade * 100:.1f}%
- Entry Price: ${entry_price:.2f}
- Stop Loss: ${stop_loss:.2f}

Calculate:
1. Dollar amount at risk
2. Risk per share (entry - stop)
3. Maximum shares to buy
4. Total position value
5. Verify position doesn't exceed concentration limits

Show all calculations step-by-step."""

        return await self.reason(query, require_confidence=False)

    def _parse_reasoning_response(self, response: LocalLLMResponse) -> dict[str, Any]:
        """Parse OpenThinker response into structured format."""
        content = response.content
        result = {
            "success": True,
            "reasoning": content,
            "decision": "HOLD",
            "confidence": 0.5,
            "key_factors": [],
            "risks": [],
        }

        # Extract decision
        content_upper = content.upper()
        if "BUY" in content_upper and "SELL" not in content_upper:
            result["decision"] = "BUY"
        elif "SELL" in content_upper:
            result["decision"] = "SELL"

        # Extract confidence
        import re

        confidence_match = re.search(
            r"confidence[:\s]+(\d+\.?\d*)", content.lower()
        )
        if confidence_match:
            try:
                result["confidence"] = min(1.0, max(0.0, float(confidence_match.group(1))))
            except ValueError:
                pass

        # Extract key factors (look for bullet points after KEY_FACTORS)
        factors_match = re.search(
            r"key_factors?[:\s]*\n?([-•*].*?)(?=\n\n|RISKS|$)",
            content,
            re.IGNORECASE | re.DOTALL,
        )
        if factors_match:
            factors_text = factors_match.group(1)
            result["key_factors"] = [
                line.strip("- •*").strip()
                for line in factors_text.split("\n")
                if line.strip()
            ]

        # Extract risks
        risks_match = re.search(
            r"risks?[:\s]*\n?([-•*].*?)(?=\n\n|$)",
            content,
            re.IGNORECASE | re.DOTALL,
        )
        if risks_match:
            risks_text = risks_match.group(1)
            result["risks"] = [
                line.strip("- •*").strip()
                for line in risks_text.split("\n")
                if line.strip()
            ]

        return result

    async def is_available(self) -> bool:
        """Check if OpenThinker is available."""
        return await self.client.is_available()

    async def close(self):
        """Close the client."""
        await self.client.close()


def _format_context(context: dict[str, Any]) -> str:
    """Format context dictionary for prompt."""
    import json

    return json.dumps(context, indent=2, default=str)


# Convenience function
async def get_openthinker_reasoner(
    model: LocalModel = LocalModel.OPENTHINKER_7B,
) -> OpenThinkerReasoner:
    """
    Get an OpenThinker reasoner instance.

    Args:
        model: OpenThinker model variant

    Returns:
        Configured OpenThinkerReasoner instance
    """
    reasoner = OpenThinkerReasoner(model=model)

    # Check availability
    if not await reasoner.is_available():
        logger.warning(
            f"OpenThinker ({model.value}) not available. "
            "Run: ollama pull openthinker:7b"
        )

    return reasoner


# Example usage
if __name__ == "__main__":

    async def main():
        # Initialize reasoner
        reasoner = OpenThinkerReasoner()

        # Check availability
        available = await reasoner.is_available()
        print(f"OpenThinker available: {available}")

        if available:
            # Test reasoning
            result = await reasoner.analyze_trade(
                symbol="AAPL",
                action="BUY",
                market_data={
                    "price": 185.50,
                    "change_pct": 1.2,
                    "rsi": 55,
                    "macd_signal": "bullish",
                    "volume": 45000000,
                },
            )

            print("\n=== Trade Analysis ===")
            print(f"Decision: {result['decision']}")
            print(f"Confidence: {result['confidence']}")
            print(f"Latency: {result['latency']:.2f}s")
            print(f"\nReasoning:\n{result['reasoning'][:500]}...")

            if result.get("thinking"):
                print(f"\nThinking Process:\n{result['thinking'][:500]}...")

        await reasoner.close()

    asyncio.run(main())
