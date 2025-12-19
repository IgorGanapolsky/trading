"""
Gemini 3 Agent - Enhanced AI agent using Google Gemini 3 API

This agent leverages Gemini 3's advanced features:
- Temperature-based reasoning depth control
- Conversation history for stateful multi-step execution
- Multimodal capabilities with adjustable fidelity
- Large context window with consistent reasoning

Note: "thinking_level" and "thought_signatures" are conceptual features
implemented via temperature adjustments and conversation history, not direct API parameters.
"""

import json
import logging
import os
from datetime import datetime
from typing import Any

import google.generativeai as genai
from src.utils.self_healing import health_check, with_retry

# Try to import GenerationConfig, fallback to dict if not available
try:
    from google.generativeai.types import GenerationConfig
except ImportError:
    # Fallback: use dict format (also supported by API)
    GenerationConfig = dict

logger = logging.getLogger(__name__)


class GeminiAgent:
    """
    Gemini 3-powered agent for trading decisions.

    Features:
    - Temperature-based reasoning control (lower = focused, higher = creative)
    - Conversation history for stateful reasoning
    - Multimodal analysis support
    - Self-healing retry mechanisms
    """

    # Temperature mapping for "thinking levels" (conceptual, not API parameter)
    THINKING_TEMPERATURES = {
        "low": 0.3,  # Focused, deterministic
        "medium": 0.7,  # Balanced
        "high": 1.0,  # Creative, exploratory
    }

    def __init__(
        self,
        name: str,
        role: str,
        model: str = "gemini-3-pro-preview",
        default_thinking_level: str = "medium",
    ):
        """
        Initialize Gemini 3 agent.

        Args:
            name: Agent name
            role: Agent role/responsibility
            model: Gemini model to use
            default_thinking_level: Conceptual reasoning depth (low/medium/high)
                                    Maps to temperature: low=0.3, medium=0.7, high=1.0
        """
        self.name = name
        self.role = role
        self.model = model
        self.default_thinking_level = default_thinking_level

        # Configure Gemini API
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            logger.warning("GOOGLE_API_KEY not found, Gemini agent will not function")
            self.client = None
        else:
            genai.configure(api_key=api_key)
            # Initialize model
            self.client = genai.GenerativeModel(model)

        # Memory and decision tracking
        self.memory: list[dict[str, Any]] = []
        self.decision_log: list[dict[str, Any]] = []
        self.conversation_history: list[dict[str, Any]] = []

        logger.info(f"Initialized {name} with Gemini 3 ({model})")

    @with_retry(max_attempts=3, backoff=2.0)
    def reason(
        self,
        prompt: str,
        thinking_level: str | None = None,
        tools: list[dict] | None = None,
        context: list[dict] | None = None,
    ) -> dict[str, Any]:
        """
        Use Gemini 3 reasoning to make decisions.

        Args:
            prompt: The reasoning prompt
            thinking_level: Conceptual reasoning depth (low/medium/high),
                           maps to temperature, defaults to agent's default
            tools: Optional tool definitions for function calling
            context: Optional conversation context (list of message dicts)

        Returns:
            Response with reasoning, decision, and metadata
        """
        if not self.client:
            logger.error("Gemini client not initialized")
            return {
                "reasoning": "Error: Gemini client not initialized",
                "decision": "NO_ACTION",
                "confidence": 0.0,
                "tool_calls": [],
                "thinking_level": thinking_level or self.default_thinking_level,
            }

        thinking_level = thinking_level or self.default_thinking_level
        temperature = self.THINKING_TEMPERATURES.get(thinking_level, 0.7)

        try:
            # Build generation config
            # Use GenerationConfig object if available, otherwise dict (both work)
            if GenerationConfig is dict:
                generation_config = {
                    "temperature": temperature,
                    "top_p": 0.95,
                    "top_k": 40,
                    "max_output_tokens": 4096,
                }
            else:
                generation_config = GenerationConfig(
                    temperature=temperature,
                    top_p=0.95,
                    top_k=40,
                    max_output_tokens=4096,
                )

            # Build conversation history
            # For single message, use simple string format
            # For multi-turn, use proper Content format
            if context and len(context) > 0:
                # Multi-turn conversation: use proper message format
                messages = []
                for msg in context:
                    # Ensure proper format: {"role": "user"/"model", "parts": [{"text": "..."}]}
                    if isinstance(msg.get("parts"), list):
                        parts = []
                        for part in msg["parts"]:
                            if isinstance(part, str):
                                parts.append({"text": part})
                            elif isinstance(part, dict):
                                parts.append(part)
                        messages.append({"role": msg.get("role", "user"), "parts": parts})
                    else:
                        # Fallback: assume it's already in correct format
                        messages.append(msg)

                # Add current prompt
                messages.append({"role": "user", "parts": [{"text": prompt}]})

                # Generate with conversation history
                if tools:
                    response = self.client.generate_content(
                        messages, generation_config=generation_config, tools=tools
                    )
                else:
                    response = self.client.generate_content(
                        messages, generation_config=generation_config
                    )
            else:
                # Single message: use simple string format (more efficient)
                if tools:
                    response = self.client.generate_content(
                        prompt, generation_config=generation_config, tools=tools
                    )
                else:
                    response = self.client.generate_content(
                        prompt, generation_config=generation_config
                    )

            # Store in conversation history
            self.conversation_history.append({"role": "user", "parts": [{"text": prompt}]})
            self.conversation_history.append({"role": "model", "parts": [{"text": response.text}]})

            # Keep history manageable (last 20 messages)
            if len(self.conversation_history) > 20:
                self.conversation_history = self.conversation_history[-20:]

            # Parse response
            result = {
                "reasoning": response.text if hasattr(response, "text") else "",
                "decision": "",
                "confidence": 0.0,
                "tool_calls": [],
                "thinking_level": thinking_level,
                "temperature": temperature,
            }

            # Extract function calls if present
            if hasattr(response, "function_calls") and response.function_calls:
                for call in response.function_calls:
                    result["tool_calls"].append(
                        {
                            "name": call.name,
                            "args": (
                                dict(call.args) if hasattr(call.args, "__dict__") else call.args
                            ),
                        }
                    )

            return result

        except Exception as e:
            logger.error(f"{self.name} Gemini reasoning error: {e}")
            return {
                "reasoning": f"Error: {str(e)}",
                "decision": "NO_ACTION",
                "confidence": 0.0,
                "tool_calls": [],
                "thinking_level": thinking_level,
                "temperature": temperature,
            }

    def analyze_with_context(
        self, data: dict[str, Any], thinking_level: str = "high"
    ) -> dict[str, Any]:
        """
        Analyze data with full context preservation using conversation history.

        Args:
            data: Input data for analysis
            thinking_level: Conceptual reasoning depth for this analysis

        Returns:
            Analysis results with preserved context
        """
        # Use recent conversation history as context
        context = self.conversation_history[-10:] if self.conversation_history else []

        # Build analysis prompt
        prompt = self._build_analysis_prompt(data)

        # Reason with context
        result = self.reason(prompt=prompt, thinking_level=thinking_level, context=context)

        # Log decision
        self.log_decision(result)

        return result

    def _build_analysis_prompt(self, data: dict[str, Any]) -> str:
        """Build analysis prompt from data."""
        return f"""You are {self.name}, responsible for: {self.role}

Analyze the following data and provide your recommendation:

{json.dumps(data, indent=2)}

Provide:
1. Your reasoning
2. Recommended action
3. Confidence level (0-1)
4. Key factors influencing your decision
"""

    def log_decision(self, decision: dict[str, Any]) -> None:
        """Log a decision for audit trail."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": self.name,
            "decision": decision,
            "thinking_level": decision.get("thinking_level"),
            "temperature": decision.get("temperature"),
        }
        self.decision_log.append(entry)
        logger.info(f"{self.name} decision logged")

    def get_memory_context(self, limit: int = 10) -> str:
        """Get recent memory context for reasoning."""
        recent_memories = self.memory[-limit:]
        if not recent_memories:
            return "No previous experience."

        context = "Recent experience:\n"
        for mem in recent_memories:
            outcome = mem.get("outcome", {})
            context += f"- {mem['timestamp']}: {outcome.get('result', 'N/A')}\n"

        return context

    def health_check(self) -> bool:
        """Run health check on agent."""
        return health_check(threshold=5, window_seconds=3600)
