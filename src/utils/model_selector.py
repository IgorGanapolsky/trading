"""
Budget-Aware Model Selector - BATS Framework Implementation

Based on Google's Budget-Aware Test-time Scaling (BATS) research.
Reference: https://arxiv.org/abs/2511.17006

Updated January 2026 with evidence-based model selection:
- StockBench benchmark: Kimi K2 ranked #1 for trading (0.0420 Sortino)
- Mistral Medium 3: 90% of Sonnet quality at 8x cheaper
- TradingAgents framework (arXiv:2412.20138) validates task-specific routing

This module provides intelligent model selection based on:
1. Task complexity (simple → DeepSeek, medium → Mistral, complex → Kimi K2)
2. Budget remaining (use cheaper models when budget is low)
3. Operational criticality (always use Opus for trade execution)

OPERATIONAL INTEGRITY RULES:
- Trade execution ALWAYS uses Opus (no cost-cutting on money decisions)
- Fallback chain: Opus → Kimi K2 → Mistral → DeepSeek (never fail completely)
- All model switches are logged for audit trail

January 2026 Pricing (per 1M tokens):
- DeepSeek V3:      $0.14 input / $0.28 output (via OpenRouter)
- Mistral Medium 3: $0.40 input / $2.00 output (via OpenRouter)
- Kimi K2:          $0.39 input / $1.90 output (via OpenRouter) - #1 trading benchmark
- Claude Opus 4.5:  $15 input / $75 output (CRITICAL only)

Sources:
- https://neurohive.io/en/news/kimi-k2-and-qwen3-235b-ins-best-ai-models-for-stock-trading-chinese-researchers-found/
- https://mistral.ai/news/mistral-medium-3
- https://arxiv.org/abs/2412.20138
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class TaskComplexity(Enum):
    """Task complexity levels for model routing."""

    SIMPLE = "simple"  # Classification, parsing, simple Q&A
    MEDIUM = "medium"  # Analysis, planning, multi-step reasoning
    COMPLEX = "complex"  # Trade decisions, risk assessment, architecture
    CRITICAL = "critical"  # Trade execution, money movement (ALWAYS Opus)


class ModelTier(Enum):
    """Model tiers with January 2026 evidence-based pricing."""

    # Cost-optimized tiers (via OpenRouter)
    DEEPSEEK = "deepseek"  # SIMPLE tasks - $0.14/$0.28 per M tokens
    MISTRAL = "mistral"  # MEDIUM tasks - $0.40/$2.00 per M tokens (90% Sonnet quality)
    KIMI = "kimi"  # COMPLEX tasks - $0.39/$1.90 per M tokens (#1 trading benchmark)
    # Premium tier (direct Anthropic API)
    OPUS = "opus"  # CRITICAL only - $15/$75 per M tokens
    # Legacy tiers (for backwards compatibility)
    HAIKU = "haiku"
    SONNET = "sonnet"


@dataclass
class ModelConfig:
    """Configuration for a specific model."""

    model_id: str
    tier: ModelTier
    input_cost_per_1m: float  # $ per 1M input tokens
    output_cost_per_1m: float  # $ per 1M output tokens
    max_context: int
    provider: str = "anthropic"  # "anthropic" or "openrouter"
    supports_extended_thinking: bool = False
    trading_sortino: float | None = None  # StockBench benchmark score (higher = better)


# January 2026 Model Registry (evidence-based selection)
# Sources: StockBench benchmark, Mistral AI, arXiv:2412.20138
MODEL_REGISTRY: dict[ModelTier, ModelConfig] = {
    # === COST-OPTIMIZED TIERS (via OpenRouter) ===
    ModelTier.DEEPSEEK: ModelConfig(
        model_id="deepseek/deepseek-chat",
        tier=ModelTier.DEEPSEEK,
        input_cost_per_1m=0.14,
        output_cost_per_1m=0.28,
        max_context=128000,
        provider="openrouter",
        trading_sortino=0.0210,  # StockBench: DeepSeek-V3.1
    ),
    ModelTier.MISTRAL: ModelConfig(
        model_id="mistralai/mistral-medium-3",
        tier=ModelTier.MISTRAL,
        input_cost_per_1m=0.40,
        output_cost_per_1m=2.00,
        max_context=128000,
        provider="openrouter",
        # 90% of Sonnet quality at 8x cheaper (Mistral AI claim)
    ),
    ModelTier.KIMI: ModelConfig(
        model_id="moonshotai/kimi-k2-0905",
        tier=ModelTier.KIMI,
        input_cost_per_1m=0.39,
        output_cost_per_1m=1.90,
        max_context=256000,
        provider="openrouter",
        trading_sortino=0.0420,  # StockBench: #1 ranked for trading
    ),
    # === PREMIUM TIER (Anthropic API) ===
    ModelTier.OPUS: ModelConfig(
        model_id="claude-opus-4-5-20251101",
        tier=ModelTier.OPUS,
        input_cost_per_1m=15.0,
        output_cost_per_1m=75.0,
        max_context=200000,
        provider="anthropic",
        supports_extended_thinking=True,
        trading_sortino=None,  # Not benchmarked, but best for compliance/safety
    ),
    # === LEGACY TIERS (backwards compatibility) ===
    ModelTier.HAIKU: ModelConfig(
        model_id="claude-3-5-haiku-20241022",
        tier=ModelTier.HAIKU,
        input_cost_per_1m=1.0,
        output_cost_per_1m=5.0,
        max_context=200000,
        provider="anthropic",
    ),
    ModelTier.SONNET: ModelConfig(
        model_id="claude-sonnet-4-5-20250929",
        tier=ModelTier.SONNET,
        input_cost_per_1m=3.0,
        output_cost_per_1m=15.0,
        max_context=200000,
        provider="anthropic",
        trading_sortino=0.0245,  # StockBench: Claude-4-Sonnet
    ),
}

# Task type to complexity mapping
TASK_COMPLEXITY_MAP: dict[str, TaskComplexity] = {
    # SIMPLE tasks - use Haiku
    "sentiment_classification": TaskComplexity.SIMPLE,
    "text_parsing": TaskComplexity.SIMPLE,
    "data_extraction": TaskComplexity.SIMPLE,
    "summarization": TaskComplexity.SIMPLE,
    "notification": TaskComplexity.SIMPLE,
    "logging": TaskComplexity.SIMPLE,
    # MEDIUM tasks - use Sonnet
    "technical_analysis": TaskComplexity.MEDIUM,
    "market_research": TaskComplexity.MEDIUM,
    "signal_generation": TaskComplexity.MEDIUM,
    "portfolio_analysis": TaskComplexity.MEDIUM,
    "news_analysis": TaskComplexity.MEDIUM,
    "pattern_recognition": TaskComplexity.MEDIUM,
    # COMPLEX tasks - use Opus when budget allows
    "strategy_planning": TaskComplexity.COMPLEX,
    "risk_assessment": TaskComplexity.COMPLEX,
    "options_analysis": TaskComplexity.COMPLEX,
    "multi_agent_coordination": TaskComplexity.COMPLEX,
    "architecture_decision": TaskComplexity.COMPLEX,
    # CRITICAL tasks - ALWAYS use Opus (no cost-cutting)
    "trade_execution": TaskComplexity.CRITICAL,
    "order_placement": TaskComplexity.CRITICAL,
    "position_sizing": TaskComplexity.CRITICAL,
    "stop_loss_calculation": TaskComplexity.CRITICAL,
    "approval_decision": TaskComplexity.CRITICAL,
}


class ModelSelector:
    """
    Budget-aware model selector implementing BATS framework.

    Safety guarantees:
    1. CRITICAL tasks always use Opus (operational integrity)
    2. Fallback chain ensures no complete failures
    3. All decisions are logged for audit trail
    4. Budget tracking prevents overruns
    """

    def __init__(
        self,
        daily_budget: float = 0.83,  # $25/month ÷ 30 days (optimized target)
        monthly_budget: float = 25.0,  # Reduced from $100 with cost-optimized models
        force_model: str | None = None,  # Override for testing
    ):
        self.daily_budget = daily_budget
        self.monthly_budget = monthly_budget
        self.force_model = force_model or os.getenv("FORCE_LLM_MODEL")

        # Track spending
        self.daily_spend = 0.0
        self.monthly_spend = 0.0
        self.last_reset_date = datetime.now().date()

        # Decision log for audit
        self.selection_log: list[dict[str, Any]] = []

        logger.info(
            f"ModelSelector initialized: daily=${daily_budget:.2f}, monthly=${monthly_budget:.2f}"
        )

    def _reset_daily_if_needed(self) -> None:
        """Reset daily spend at midnight."""
        today = datetime.now().date()
        if today != self.last_reset_date:
            logger.info(
                f"Daily budget reset: ${self.daily_spend:.2f} spent on {self.last_reset_date}"
            )
            self.daily_spend = 0.0
            self.last_reset_date = today

            # Monthly reset on 1st
            if today.day == 1:
                logger.info(f"Monthly budget reset: ${self.monthly_spend:.2f} spent")
                self.monthly_spend = 0.0

    def get_task_complexity(self, task_type: str) -> TaskComplexity:
        """
        Determine task complexity from task type string.

        Unknown tasks default to MEDIUM for safety.
        """
        complexity = TASK_COMPLEXITY_MAP.get(task_type.lower())
        if complexity is None:
            logger.warning(f"Unknown task type '{task_type}', defaulting to MEDIUM complexity")
            return TaskComplexity.MEDIUM
        return complexity

    def can_afford_model(self, tier: ModelTier, estimated_tokens: int = 2000) -> bool:
        """
        Check if we can afford to use a model tier.

        Args:
            tier: Model tier to check
            estimated_tokens: Estimated total tokens (input + output)

        Returns:
            True if within budget, False if would exceed daily limit
        """
        config = MODEL_REGISTRY[tier]
        # Assume 60/40 split input/output for estimation
        input_tokens = int(estimated_tokens * 0.6)
        output_tokens = int(estimated_tokens * 0.4)
        estimated_cost = (input_tokens / 1_000_000) * config.input_cost_per_1m + (
            output_tokens / 1_000_000
        ) * config.output_cost_per_1m
        return (self.daily_spend + estimated_cost) <= self.daily_budget

    def enforce_budget(
        self,
        model_id: str,
        estimated_tokens: int = 2000,
    ) -> tuple[bool, str]:
        """
        Enforce budget BEFORE making an API call.

        Args:
            model_id: Model to use
            estimated_tokens: Estimated total tokens

        Returns:
            (allowed, reason) - allowed=True if call should proceed,
            or (False, reason) with explanation if blocked

        CRITICAL tasks are NEVER blocked (operational integrity).
        """
        self._reset_daily_if_needed()

        config = self.get_model_config(model_id)
        if config is None:
            return True, "unknown_model_allowed"

        # CRITICAL tier is never blocked
        if config.tier == ModelTier.OPUS:
            return True, "critical_always_allowed"

        # Estimate cost
        input_tokens = int(estimated_tokens * 0.6)
        output_tokens = int(estimated_tokens * 0.4)
        estimated_cost = (input_tokens / 1_000_000) * config.input_cost_per_1m + (
            output_tokens / 1_000_000
        ) * config.output_cost_per_1m

        if (self.daily_spend + estimated_cost) > self.daily_budget:
            overage = (self.daily_spend + estimated_cost) - self.daily_budget
            logger.warning(
                f"BUDGET ENFORCEMENT: Blocking {model_id} call - "
                f"would exceed daily budget by ${overage:.4f}"
            )
            return False, f"budget_exceeded_by_{overage:.4f}"

        return True, "within_budget"

    def select_model(
        self,
        task_type: str,
        force_tier: ModelTier | None = None,
        enforce_budget: bool = True,
    ) -> str:
        """
        Select the appropriate model based on task and budget.

        Args:
            task_type: Type of task (see TASK_COMPLEXITY_MAP)
            force_tier: Optional override to force a specific tier
            enforce_budget: If True, downgrade model if budget exceeded (default: True)

        Returns:
            Model ID string for API calls

        SAFETY: CRITICAL tasks always return Opus regardless of budget.
        """
        self._reset_daily_if_needed()

        # Check for forced model (testing/override)
        if self.force_model:
            logger.info(f"Using forced model: {self.force_model}")
            return self.force_model

        # Get task complexity
        complexity = self.get_task_complexity(task_type)

        # CRITICAL tasks ALWAYS use Opus - no cost-cutting on money decisions
        if complexity == TaskComplexity.CRITICAL:
            selected = MODEL_REGISTRY[ModelTier.OPUS]
            self._log_selection(task_type, complexity, selected, "CRITICAL_OVERRIDE")
            return selected.model_id

        # Honor explicit tier override
        if force_tier:
            selected = MODEL_REGISTRY[force_tier]
            self._log_selection(task_type, complexity, selected, "FORCE_TIER")
            return selected.model_id

        # Budget-aware selection
        budget_remaining = self.daily_budget - self.daily_spend
        budget_pct = budget_remaining / self.daily_budget if self.daily_budget > 0 else 0

        # Check if OpenRouter is available (required for cost-optimized models)
        openrouter_available = bool(os.getenv("OPENROUTER_API_KEY"))

        # Determine tier based on complexity and budget
        # January 2026 evidence-based routing (StockBench, TradingAgents framework)
        if complexity == TaskComplexity.SIMPLE:
            # SIMPLE → DeepSeek V3 ($0.14/$0.28) - fast, efficient
            if openrouter_available:
                tier = ModelTier.DEEPSEEK
                reason = "SIMPLE_TASK_DEEPSEEK"
            else:
                tier = ModelTier.HAIKU
                reason = "SIMPLE_TASK_HAIKU_FALLBACK"
        elif complexity == TaskComplexity.MEDIUM:
            # MEDIUM → Mistral Medium 3 ($0.40/$2.00) - 90% Sonnet quality
            if openrouter_available:
                tier = ModelTier.MISTRAL
                reason = "MEDIUM_TASK_MISTRAL"
            elif budget_pct > 0.3:
                tier = ModelTier.SONNET
                reason = "MEDIUM_TASK_SONNET_FALLBACK"
            else:
                tier = ModelTier.HAIKU
                reason = "MEDIUM_TASK_HAIKU_FALLBACK"
        elif complexity == TaskComplexity.COMPLEX:
            # COMPLEX → Kimi K2 ($0.39/$1.90) - #1 trading benchmark (0.0420 Sortino)
            if openrouter_available:
                tier = ModelTier.KIMI
                reason = "COMPLEX_TASK_KIMI_K2"
            elif budget_pct > 0.5:
                tier = ModelTier.OPUS
                reason = "COMPLEX_TASK_OPUS_FALLBACK"
            elif budget_pct > 0.2:
                tier = ModelTier.SONNET
                reason = "COMPLEX_TASK_SONNET_FALLBACK"
            else:
                tier = ModelTier.HAIKU
                reason = "COMPLEX_TASK_LOW_BUDGET"
        else:
            # Fallback to Mistral or Sonnet
            if openrouter_available:
                tier = ModelTier.MISTRAL
                reason = "FALLBACK_MISTRAL"
            else:
                tier = ModelTier.SONNET
                reason = "FALLBACK_SONNET"

        # BUDGET ENFORCEMENT: Downgrade if selected tier would exceed budget
        if enforce_budget and not self.can_afford_model(tier):
            original_tier = tier
            # Downgrade chain: KIMI → MISTRAL → DEEPSEEK → HAIKU
            downgrade_chain = [ModelTier.MISTRAL, ModelTier.DEEPSEEK, ModelTier.HAIKU]
            for fallback_tier in downgrade_chain:
                if self.can_afford_model(fallback_tier):
                    tier = fallback_tier
                    reason = f"BUDGET_DOWNGRADE_FROM_{original_tier.value.upper()}"
                    logger.warning(
                        f"Budget enforcement: downgraded {original_tier.value} → {tier.value} "
                        f"(${self.daily_spend:.2f}/${self.daily_budget:.2f} daily)"
                    )
                    break
            else:
                # Even HAIKU exceeds budget - log but allow (never completely block)
                logger.error(
                    f"BUDGET EXHAUSTED: All models exceed daily budget! "
                    f"Allowing {tier.value} anyway. Spent: ${self.daily_spend:.2f}"
                )
                reason = "BUDGET_EXHAUSTED_ALLOWED"

        selected = MODEL_REGISTRY[tier]
        self._log_selection(task_type, complexity, selected, reason)
        return selected.model_id

    def log_usage(
        self,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """
        Log API usage and return cost.

        Call this after each API call to track spending.
        """
        # Find model config
        config = None
        for model_config in MODEL_REGISTRY.values():
            if model_config.model_id == model_id:
                config = model_config
                break

        if config is None:
            logger.warning(f"Unknown model {model_id}, using Sonnet pricing")
            config = MODEL_REGISTRY[ModelTier.SONNET]

        # Calculate cost
        input_cost = (input_tokens / 1_000_000) * config.input_cost_per_1m
        output_cost = (output_tokens / 1_000_000) * config.output_cost_per_1m
        total_cost = input_cost + output_cost

        # Update spending
        self.daily_spend += total_cost
        self.monthly_spend += total_cost

        logger.debug(
            f"API usage: {model_id} - {input_tokens}in/{output_tokens}out = "
            f"${total_cost:.4f} (daily: ${self.daily_spend:.2f})"
        )

        return total_cost

    def _log_selection(
        self,
        task_type: str,
        complexity: TaskComplexity,
        selected: ModelConfig,
        reason: str,
    ) -> None:
        """Log model selection for audit trail."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "task_type": task_type,
            "complexity": complexity.value,
            "selected_model": selected.model_id,
            "selected_tier": selected.tier.value,
            "reason": reason,
            "daily_spend": self.daily_spend,
            "daily_budget": self.daily_budget,
        }
        self.selection_log.append(entry)

        # Keep log bounded (last 1000 entries)
        if len(self.selection_log) > 1000:
            self.selection_log = self.selection_log[-500:]

        logger.info(
            f"Model selected: {selected.tier.value.upper()} ({selected.model_id}) "
            f"for {task_type} [{reason}] "
            f"(budget: ${self.daily_spend:.2f}/${self.daily_budget:.2f})"
        )

    def get_budget_status(self) -> dict[str, Any]:
        """Get current budget status for monitoring."""
        self._reset_daily_if_needed()
        return {
            "daily_spent": self.daily_spend,
            "daily_budget": self.daily_budget,
            "daily_remaining": self.daily_budget - self.daily_spend,
            "daily_pct_used": (self.daily_spend / self.daily_budget * 100)
            if self.daily_budget > 0
            else 0,
            "monthly_spent": self.monthly_spend,
            "monthly_budget": self.monthly_budget,
            "monthly_remaining": self.monthly_budget - self.monthly_spend,
        }

    def get_model_provider(self, model_id: str) -> str:
        """
        Get the API provider for a model ID.

        Returns:
            "anthropic" for Claude models, "openrouter" for cost-optimized models
        """
        for config in MODEL_REGISTRY.values():
            if config.model_id == model_id:
                return config.provider
        # Default to anthropic for unknown models
        return "anthropic"

    def get_model_config(self, model_id: str) -> ModelConfig | None:
        """Get full configuration for a model ID."""
        for config in MODEL_REGISTRY.values():
            if config.model_id == model_id:
                return config
        return None

    def get_model_for_agent(self, agent_name: str) -> str:
        """
        Get recommended model for a specific agent type.

        Maps agent names to appropriate task types for model selection.
        """
        agent_task_map = {
            # Simple agents - use Haiku
            "NotificationAgent": "notification",
            # Medium complexity - use Sonnet
            "SignalAgent": "signal_generation",
            "ResearchAgent": "market_research",
            "MetaAgent": "portfolio_analysis",
            "BogleHeadsAgent": "market_research",
            "GammaExposureAgent": "options_analysis",
            # High complexity - use Opus when budget allows
            "RiskAgent": "risk_assessment",
            "WorkflowAgent": "strategy_planning",
            # Critical - ALWAYS Opus
            "ExecutionAgent": "trade_execution",
            "ApprovalAgent": "approval_decision",
        }

        task_type = agent_task_map.get(agent_name, "technical_analysis")
        return self.select_model(task_type)


# Singleton instance for global access
_model_selector: ModelSelector | None = None


def get_model_selector() -> ModelSelector:
    """Get or create the global ModelSelector instance."""
    global _model_selector
    if _model_selector is None:
        # Read budget from environment or use optimized defaults
        # January 2026: $25/month target with cost-optimized models
        daily_budget = float(os.getenv("LLM_DAILY_BUDGET", "0.83"))
        monthly_budget = float(os.getenv("LLM_MONTHLY_BUDGET", "25.0"))
        _model_selector = ModelSelector(
            daily_budget=daily_budget,
            monthly_budget=monthly_budget,
        )
    return _model_selector


def select_model_for_task(task_type: str) -> str:
    """Convenience function for model selection."""
    return get_model_selector().select_model(task_type)
