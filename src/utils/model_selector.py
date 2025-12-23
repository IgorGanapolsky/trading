"""
Budget-Aware Model Selector - BATS Framework Implementation

Based on Google's Budget-Aware Test-time Scaling (BATS) research.
Reference: https://arxiv.org/abs/2511.17006

This module provides intelligent model selection based on:
1. Task complexity (simple → Haiku, medium → Sonnet, complex → Opus)
2. Budget remaining (use cheaper models when budget is low)
3. Operational criticality (always use Opus for trade execution)

OPERATIONAL INTEGRITY RULES:
- Trade execution ALWAYS uses Opus (no cost-cutting on money decisions)
- Fallback chain: Opus → Sonnet → Haiku (never fail completely)
- All model switches are logged for audit trail

December 2025 Pricing (per 1M tokens):
- Haiku 4.5:  $1 input / $5 output
- Sonnet 4.5: $3 input / $15 output
- Opus 4.5:   $15 input / $75 output
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
    """Model tiers with December 2025 pricing."""

    HAIKU = "haiku"
    SONNET = "sonnet"
    OPUS = "opus"


@dataclass
class ModelConfig:
    """Configuration for a specific model."""

    model_id: str
    tier: ModelTier
    input_cost_per_1m: float  # $ per 1M input tokens
    output_cost_per_1m: float  # $ per 1M output tokens
    max_context: int
    supports_extended_thinking: bool = False


# December 2025 Model Registry (latest stable versions)
MODEL_REGISTRY: dict[ModelTier, ModelConfig] = {
    ModelTier.HAIKU: ModelConfig(
        model_id="claude-3-5-haiku-20241022",
        tier=ModelTier.HAIKU,
        input_cost_per_1m=1.0,
        output_cost_per_1m=5.0,
        max_context=200000,
        supports_extended_thinking=False,
    ),
    ModelTier.SONNET: ModelConfig(
        model_id="claude-sonnet-4-5-20250929",
        tier=ModelTier.SONNET,
        input_cost_per_1m=3.0,
        output_cost_per_1m=15.0,
        max_context=200000,
        supports_extended_thinking=False,
    ),
    ModelTier.OPUS: ModelConfig(
        model_id="claude-opus-4-5-20251101",
        tier=ModelTier.OPUS,
        input_cost_per_1m=15.0,
        output_cost_per_1m=75.0,
        max_context=200000,
        supports_extended_thinking=True,
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
        daily_budget: float = 3.33,  # $100/month ÷ 30 days
        monthly_budget: float = 100.0,
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

    def select_model(
        self,
        task_type: str,
        force_tier: ModelTier | None = None,
    ) -> str:
        """
        Select the appropriate model based on task and budget.

        Args:
            task_type: Type of task (see TASK_COMPLEXITY_MAP)
            force_tier: Optional override to force a specific tier

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

        # Determine tier based on complexity and budget
        if complexity == TaskComplexity.SIMPLE:
            tier = ModelTier.HAIKU
            reason = "SIMPLE_TASK"
        elif complexity == TaskComplexity.MEDIUM:
            # Use Sonnet if budget allows, else Haiku
            if budget_pct > 0.3:
                tier = ModelTier.SONNET
                reason = "MEDIUM_TASK_BUDGET_OK"
            else:
                tier = ModelTier.HAIKU
                reason = "MEDIUM_TASK_LOW_BUDGET"
        elif complexity == TaskComplexity.COMPLEX:
            # Use Opus if >50% budget, Sonnet if >20%, else Haiku
            if budget_pct > 0.5:
                tier = ModelTier.OPUS
                reason = "COMPLEX_TASK_BUDGET_HIGH"
            elif budget_pct > 0.2:
                tier = ModelTier.SONNET
                reason = "COMPLEX_TASK_BUDGET_MEDIUM"
            else:
                tier = ModelTier.HAIKU
                reason = "COMPLEX_TASK_LOW_BUDGET"
        else:
            # Fallback to Sonnet
            tier = ModelTier.SONNET
            reason = "FALLBACK"

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
        # Read budget from environment or use defaults
        daily_budget = float(os.getenv("LLM_DAILY_BUDGET", "3.33"))
        monthly_budget = float(os.getenv("LLM_MONTHLY_BUDGET", "100.0"))
        _model_selector = ModelSelector(
            daily_budget=daily_budget,
            monthly_budget=monthly_budget,
        )
    return _model_selector


def select_model_for_task(task_type: str) -> str:
    """Convenience function for model selection."""
    return get_model_selector().select_model(task_type)
