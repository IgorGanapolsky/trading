"""
Anthropic Agent Patterns Implementation

Based on Anthropic's "Building Effective Agents" guidance:
https://www.anthropic.com/engineering/building-effective-agents

Implements:
1. Risk-based human-in-the-loop checkpoints
2. Unified error recovery with tool fallbacks
3. Evaluator-Optimizer loop for continuous improvement
4. Action-oriented tool design patterns
"""

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# 1. RISK-BASED HUMAN-IN-THE-LOOP CHECKPOINTS
# =============================================================================


class RiskLevel(Enum):
    """Risk levels requiring different approval thresholds."""
    LOW = "low"           # Auto-approve
    MEDIUM = "medium"     # Log + proceed
    HIGH = "high"         # Require confirmation
    CRITICAL = "critical" # Block until CEO approval


@dataclass
class RiskCheckpoint:
    """
    Human-in-the-loop checkpoint based on Anthropic's patterns.

    Key insight: Approval thresholds should be MULTI-DIMENSIONAL,
    not just based on trade value.
    """
    trade_value_threshold: float = 50.0  # $50 for high-risk flag
    daily_loss_threshold: float = 0.02   # 2% daily loss triggers checkpoint
    consecutive_losses: int = 3          # 3 losses in a row
    volatility_multiplier: float = 2.0   # 2x normal volatility
    correlation_threshold: float = 0.8   # 80% correlation with existing positions

    def assess_risk(self, context: dict[str, Any]) -> tuple[RiskLevel, list[str]]:
        """
        Multi-dimensional risk assessment for human-in-the-loop decisions.

        Returns:
            Tuple of (risk_level, list of reasons)
        """
        reasons = []
        risk_level = RiskLevel.LOW

        trade_value = context.get("trade_value", 0)
        daily_pnl_pct = context.get("daily_pnl_pct", 0)
        consecutive_losses = context.get("consecutive_losses", 0)
        current_volatility = context.get("current_volatility", 1.0)
        normal_volatility = context.get("normal_volatility", 1.0)
        position_correlation = context.get("position_correlation", 0)

        # Check trade value
        if trade_value > self.trade_value_threshold:
            reasons.append(f"Trade value ${trade_value:.2f} > ${self.trade_value_threshold}")
            risk_level = max(risk_level, RiskLevel.HIGH, key=lambda x: list(RiskLevel).index(x))

        # Check daily loss
        if abs(daily_pnl_pct) > self.daily_loss_threshold and daily_pnl_pct < 0:
            reasons.append(f"Daily loss {daily_pnl_pct:.2%} exceeds threshold")
            risk_level = max(risk_level, RiskLevel.HIGH, key=lambda x: list(RiskLevel).index(x))

        # Check consecutive losses
        if consecutive_losses >= self.consecutive_losses:
            reasons.append(f"{consecutive_losses} consecutive losses")
            risk_level = max(risk_level, RiskLevel.CRITICAL, key=lambda x: list(RiskLevel).index(x))

        # Check volatility spike
        vol_ratio = current_volatility / normal_volatility if normal_volatility > 0 else 1
        if vol_ratio > self.volatility_multiplier:
            reasons.append(f"Volatility {vol_ratio:.1f}x normal")
            risk_level = max(risk_level, RiskLevel.MEDIUM, key=lambda x: list(RiskLevel).index(x))

        # Check position correlation
        if position_correlation > self.correlation_threshold:
            reasons.append(f"High correlation ({position_correlation:.0%}) with existing positions")
            risk_level = max(risk_level, RiskLevel.MEDIUM, key=lambda x: list(RiskLevel).index(x))

        return risk_level, reasons


@dataclass
class HumanCheckpoint:
    """
    Implements Anthropic's human-in-the-loop pattern.

    Key insight: Different risk levels require different responses:
    - LOW: Auto-proceed, log for audit
    - MEDIUM: Proceed with warning notification
    - HIGH: Pause and request confirmation (with timeout)
    - CRITICAL: Block until explicit CEO approval
    """
    checkpoint_id: str
    context: dict[str, Any]
    risk_level: RiskLevel
    reasons: list[str]
    created_at: datetime = field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    resolution: Optional[str] = None  # "approved", "rejected", "timeout", "escalated"

    def requires_human_approval(self) -> bool:
        """Determine if checkpoint requires human approval."""
        return self.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    def get_timeout_seconds(self) -> int:
        """Get appropriate timeout based on risk level."""
        timeouts = {
            RiskLevel.LOW: 0,       # No wait
            RiskLevel.MEDIUM: 0,    # No wait, just notify
            RiskLevel.HIGH: 300,    # 5 minutes
            RiskLevel.CRITICAL: 0,  # No timeout - must wait
        }
        return timeouts.get(self.risk_level, 300)


# =============================================================================
# 2. UNIFIED ERROR RECOVERY WITH TOOL FALLBACKS
# =============================================================================


class ToolFallbackStrategy(Enum):
    """Fallback strategies when a tool fails."""
    RETRY_SAME = "retry_same"           # Retry the same tool
    FALLBACK_TOOL = "fallback_tool"     # Use alternative tool
    DEGRADE_GRACEFULLY = "degrade"      # Continue without this capability
    ABORT_WORKFLOW = "abort"            # Stop the workflow entirely
    HUMAN_INTERVENTION = "human"        # Request human help


@dataclass
class ToolRecoveryConfig:
    """Configuration for tool error recovery."""
    tool_name: str
    max_retries: int = 3
    retry_backoff: float = 2.0  # Exponential backoff base
    fallback_tool: Optional[str] = None
    fallback_strategy: ToolFallbackStrategy = ToolFallbackStrategy.RETRY_SAME
    critical: bool = False  # If True, abort workflow on failure


class ErrorRecoveryFramework:
    """
    Unified error recovery based on Anthropic's patterns.

    Key insight: Tools should fail gracefully with defined recovery paths.
    """

    def __init__(self):
        self.recovery_configs: dict[str, ToolRecoveryConfig] = {}
        self.failure_log: list[dict] = []
        self._register_default_configs()

    def _register_default_configs(self):
        """Register default recovery configurations for trading tools."""
        defaults = [
            # Market data tools - can fallback to cached data
            ToolRecoveryConfig(
                tool_name="get_market_data",
                max_retries=3,
                fallback_tool="get_cached_market_data",
                fallback_strategy=ToolFallbackStrategy.FALLBACK_TOOL,
                critical=False
            ),
            # Sentiment analysis - can degrade gracefully
            ToolRecoveryConfig(
                tool_name="analyze_sentiment",
                max_retries=2,
                fallback_strategy=ToolFallbackStrategy.DEGRADE_GRACEFULLY,
                critical=False
            ),
            # Trade execution - CRITICAL, must succeed or abort
            ToolRecoveryConfig(
                tool_name="execute_trade",
                max_retries=5,
                retry_backoff=1.5,
                fallback_strategy=ToolFallbackStrategy.HUMAN_INTERVENTION,
                critical=True
            ),
            # Risk assessment - can fallback to conservative estimate
            ToolRecoveryConfig(
                tool_name="assess_risk",
                max_retries=2,
                fallback_tool="conservative_risk_estimate",
                fallback_strategy=ToolFallbackStrategy.FALLBACK_TOOL,
                critical=False
            ),
            # Position sizing - can fallback to minimum size
            ToolRecoveryConfig(
                tool_name="calculate_position_size",
                max_retries=2,
                fallback_tool="minimum_position_size",
                fallback_strategy=ToolFallbackStrategy.FALLBACK_TOOL,
                critical=False
            ),
        ]

        for config in defaults:
            self.recovery_configs[config.tool_name] = config

    def register_config(self, config: ToolRecoveryConfig):
        """Register a tool recovery configuration."""
        self.recovery_configs[config.tool_name] = config

    async def execute_with_recovery(
        self,
        tool_name: str,
        tool_func: Callable,
        *args,
        fallback_funcs: Optional[dict[str, Callable]] = None,
        **kwargs
    ) -> tuple[bool, Any, Optional[str]]:
        """
        Execute a tool with automatic error recovery.

        Returns:
            Tuple of (success, result, error_message)
        """
        config = self.recovery_configs.get(
            tool_name,
            ToolRecoveryConfig(tool_name=tool_name)  # Default config
        )

        last_error = None

        # Try the primary tool with retries
        for attempt in range(config.max_retries):
            try:
                if asyncio.iscoroutinefunction(tool_func):
                    result = await tool_func(*args, **kwargs)
                else:
                    result = tool_func(*args, **kwargs)
                return True, result, None

            except Exception as e:
                last_error = str(e)
                self._log_failure(tool_name, attempt + 1, last_error)

                if attempt < config.max_retries - 1:
                    delay = config.retry_backoff ** attempt
                    logger.warning(
                        f"Tool {tool_name} failed (attempt {attempt + 1}), "
                        f"retrying in {delay:.1f}s: {e}"
                    )
                    await asyncio.sleep(delay)

        # Primary tool exhausted retries - apply fallback strategy
        return await self._apply_fallback(
            config, fallback_funcs, last_error, *args, **kwargs
        )

    async def _apply_fallback(
        self,
        config: ToolRecoveryConfig,
        fallback_funcs: Optional[dict[str, Callable]],
        error: str,
        *args,
        **kwargs
    ) -> tuple[bool, Any, Optional[str]]:
        """Apply the configured fallback strategy."""

        strategy = config.fallback_strategy

        if strategy == ToolFallbackStrategy.FALLBACK_TOOL:
            if config.fallback_tool and fallback_funcs:
                fallback_func = fallback_funcs.get(config.fallback_tool)
                if fallback_func:
                    try:
                        logger.info(f"Using fallback tool: {config.fallback_tool}")
                        if asyncio.iscoroutinefunction(fallback_func):
                            result = await fallback_func(*args, **kwargs)
                        else:
                            result = fallback_func(*args, **kwargs)
                        return True, result, None
                    except Exception as e:
                        return False, None, f"Fallback also failed: {e}"
            return False, None, f"No fallback tool available: {error}"

        elif strategy == ToolFallbackStrategy.DEGRADE_GRACEFULLY:
            logger.warning(f"Degrading gracefully after {config.tool_name} failure")
            return True, {"degraded": True, "reason": error}, None

        elif strategy == ToolFallbackStrategy.ABORT_WORKFLOW:
            logger.error(f"Aborting workflow due to {config.tool_name} failure")
            return False, None, f"Critical tool failed: {error}"

        elif strategy == ToolFallbackStrategy.HUMAN_INTERVENTION:
            logger.critical(f"Requesting human intervention for {config.tool_name}")
            return False, None, f"Human intervention required: {error}"

        # Default: just fail
        return False, None, error

    def _log_failure(self, tool_name: str, attempt: int, error: str):
        """Log tool failure for analysis."""
        self.failure_log.append({
            "tool": tool_name,
            "attempt": attempt,
            "error": error,
            "timestamp": datetime.now().isoformat()
        })

        # Keep only last 1000 failures
        if len(self.failure_log) > 1000:
            self.failure_log = self.failure_log[-500:]


# =============================================================================
# 3. EVALUATOR-OPTIMIZER LOOP
# =============================================================================


@dataclass
class EvaluationResult:
    """Result of evaluating a trading strategy or decision."""
    score: float  # 0.0 to 1.0
    metrics: dict[str, float]
    feedback: list[str]
    suggestions: list[str]
    passed: bool


class StrategyEvaluator(ABC):
    """Abstract base for strategy evaluators."""

    @abstractmethod
    def evaluate(self, context: dict[str, Any]) -> EvaluationResult:
        """Evaluate a strategy or decision."""
        pass


class TradingStrategyEvaluator(StrategyEvaluator):
    """
    Evaluator for trading strategies.

    Checks:
    - Win rate
    - Sharpe ratio
    - Max drawdown
    - Risk-adjusted returns
    - Consistency
    """

    def __init__(
        self,
        min_win_rate: float = 0.55,
        min_sharpe: float = 1.0,
        max_drawdown: float = 0.10,
        min_trades: int = 20
    ):
        self.min_win_rate = min_win_rate
        self.min_sharpe = min_sharpe
        self.max_drawdown = max_drawdown
        self.min_trades = min_trades

    def evaluate(self, context: dict[str, Any]) -> EvaluationResult:
        """Evaluate trading strategy performance."""
        trades = context.get("trades", [])
        win_rate = context.get("win_rate", 0)
        sharpe = context.get("sharpe_ratio", 0)
        max_dd = context.get("max_drawdown", 1.0)
        total_return = context.get("total_return", 0)

        metrics = {
            "win_rate": win_rate,
            "sharpe_ratio": sharpe,
            "max_drawdown": max_dd,
            "total_return": total_return,
            "trade_count": len(trades)
        }

        feedback = []
        suggestions = []
        score = 0.0

        # Evaluate win rate
        if win_rate >= self.min_win_rate:
            score += 0.25
            feedback.append(f"✓ Win rate {win_rate:.1%} meets threshold")
        else:
            feedback.append(f"✗ Win rate {win_rate:.1%} below {self.min_win_rate:.1%}")
            suggestions.append("Consider tighter entry criteria or better signal confirmation")

        # Evaluate Sharpe ratio
        if sharpe >= self.min_sharpe:
            score += 0.25
            feedback.append(f"✓ Sharpe ratio {sharpe:.2f} meets threshold")
        else:
            feedback.append(f"✗ Sharpe ratio {sharpe:.2f} below {self.min_sharpe}")
            suggestions.append("Improve risk-adjusted returns through better position sizing")

        # Evaluate drawdown
        if max_dd <= self.max_drawdown:
            score += 0.25
            feedback.append(f"✓ Max drawdown {max_dd:.1%} within limits")
        else:
            feedback.append(f"✗ Max drawdown {max_dd:.1%} exceeds {self.max_drawdown:.1%}")
            suggestions.append("Implement tighter stop-losses or reduce position sizes")

        # Evaluate trade count
        if len(trades) >= self.min_trades:
            score += 0.25
            feedback.append(f"✓ Sufficient trades ({len(trades)}) for statistical significance")
        else:
            feedback.append(f"✗ Only {len(trades)} trades - need {self.min_trades} for significance")
            suggestions.append("Continue paper trading to gather more data")

        passed = score >= 0.75  # Need 3/4 criteria

        return EvaluationResult(
            score=score,
            metrics=metrics,
            feedback=feedback,
            suggestions=suggestions,
            passed=passed
        )


class StrategyOptimizer(ABC):
    """Abstract base for strategy optimizers."""

    @abstractmethod
    def optimize(
        self,
        evaluation: EvaluationResult,
        current_params: dict[str, Any]
    ) -> dict[str, Any]:
        """Suggest optimized parameters based on evaluation."""
        pass


class TradingStrategyOptimizer(StrategyOptimizer):
    """
    Optimizer for trading strategies.

    Uses evaluation feedback to suggest parameter adjustments.
    """

    def optimize(
        self,
        evaluation: EvaluationResult,
        current_params: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate optimized parameters based on evaluation."""
        new_params = current_params.copy()

        metrics = evaluation.metrics

        # Adjust based on win rate
        if metrics.get("win_rate", 0) < 0.55:
            # Tighten entry criteria
            if "entry_threshold" in new_params:
                new_params["entry_threshold"] *= 1.1
            if "min_confidence" in new_params:
                new_params["min_confidence"] = min(
                    new_params["min_confidence"] + 0.05, 0.95
                )

        # Adjust based on Sharpe ratio
        if metrics.get("sharpe_ratio", 0) < 1.0:
            # Reduce position sizes for better risk-adjusted returns
            if "max_position_pct" in new_params:
                new_params["max_position_pct"] *= 0.9

        # Adjust based on drawdown
        if metrics.get("max_drawdown", 0) > 0.10:
            # Tighten stop-losses
            if "stop_loss_pct" in new_params:
                new_params["stop_loss_pct"] *= 0.8
            if "max_daily_loss_pct" in new_params:
                new_params["max_daily_loss_pct"] *= 0.9

        return new_params


class EvaluatorOptimizerLoop:
    """
    Implements Anthropic's Evaluator-Optimizer pattern for continuous improvement.

    Pattern:
    1. Execute strategy with current parameters
    2. Evaluate performance
    3. If evaluation fails, optimize parameters
    4. Loop until evaluation passes or max iterations reached

    This is the key pattern for RL system improvement.
    """

    def __init__(
        self,
        evaluator: StrategyEvaluator,
        optimizer: StrategyOptimizer,
        max_iterations: int = 10,
        min_improvement: float = 0.01
    ):
        self.evaluator = evaluator
        self.optimizer = optimizer
        self.max_iterations = max_iterations
        self.min_improvement = min_improvement
        self.history: list[dict] = []

    async def run_loop(
        self,
        initial_params: dict[str, Any],
        execute_strategy: Callable[[dict], dict],
        save_params: Optional[Callable[[dict], None]] = None
    ) -> tuple[dict[str, Any], EvaluationResult]:
        """
        Run the evaluator-optimizer loop.

        Args:
            initial_params: Starting strategy parameters
            execute_strategy: Function that runs strategy and returns context
            save_params: Optional function to persist optimized params

        Returns:
            Tuple of (optimized_params, final_evaluation)
        """
        current_params = initial_params.copy()
        best_score = 0.0
        iterations_without_improvement = 0

        for iteration in range(self.max_iterations):
            logger.info(f"Evaluator-Optimizer iteration {iteration + 1}/{self.max_iterations}")

            # Execute strategy with current params
            context = execute_strategy(current_params)

            # Evaluate results
            evaluation = self.evaluator.evaluate(context)

            # Log iteration
            self.history.append({
                "iteration": iteration + 1,
                "params": current_params.copy(),
                "score": evaluation.score,
                "passed": evaluation.passed,
                "metrics": evaluation.metrics,
                "timestamp": datetime.now().isoformat()
            })

            logger.info(
                f"Iteration {iteration + 1}: score={evaluation.score:.2f}, "
                f"passed={evaluation.passed}"
            )

            # Check if we've passed
            if evaluation.passed:
                logger.info("Strategy evaluation PASSED - optimization complete")
                if save_params:
                    save_params(current_params)
                return current_params, evaluation

            # Check for improvement
            if evaluation.score > best_score + self.min_improvement:
                best_score = evaluation.score
                iterations_without_improvement = 0
            else:
                iterations_without_improvement += 1

            # Early stopping if no improvement
            if iterations_without_improvement >= 3:
                logger.warning("No improvement for 3 iterations - stopping early")
                break

            # Optimize parameters for next iteration
            current_params = self.optimizer.optimize(evaluation, current_params)

            for suggestion in evaluation.suggestions:
                logger.info(f"  Suggestion: {suggestion}")

        # Return best result even if not passed
        final_evaluation = self.evaluator.evaluate(execute_strategy(current_params))

        if save_params:
            save_params(current_params)

        return current_params, final_evaluation

    def get_improvement_report(self) -> dict[str, Any]:
        """Generate a report of the optimization process."""
        if not self.history:
            return {"status": "no_iterations"}

        first = self.history[0]
        last = self.history[-1]

        return {
            "total_iterations": len(self.history),
            "initial_score": first["score"],
            "final_score": last["score"],
            "improvement": last["score"] - first["score"],
            "passed": last["passed"],
            "history": self.history
        }


# =============================================================================
# 4. ACTION-ORIENTED TOOL DESIGN PATTERNS
# =============================================================================


@dataclass
class ActionTool:
    """
    Action-oriented tool definition based on Anthropic's guidance.

    Key insight: Tools should be ACTION verbs, not data getters.
    Bad: get_positions(), list_orders()
    Good: close_position(), execute_trade(), assess_risk()
    """
    name: str
    description: str
    action_verb: str  # The primary action: "execute", "assess", "validate"
    parameters: dict[str, Any]
    returns: str
    side_effects: list[str]  # What changes when this tool runs
    reversible: bool = True
    requires_approval: bool = False

    def validate_name(self) -> bool:
        """Validate tool name follows action-oriented pattern."""
        action_verbs = [
            "execute", "place", "cancel", "close", "assess", "validate",
            "calculate", "analyze", "detect", "monitor", "alert", "notify",
            "optimize", "rebalance", "hedge", "scale"
        ]
        return any(self.name.startswith(verb) for verb in action_verbs)


# Recommended action-oriented tool mappings
ACTION_TOOL_MAPPINGS = {
    # Instead of get_positions -> assess_portfolio_risk
    "get_positions": ActionTool(
        name="assess_portfolio_risk",
        description="Assess current portfolio risk including position sizing and correlation",
        action_verb="assess",
        parameters={"include_greeks": "bool", "correlation_window": "int"},
        returns="RiskAssessment with positions, risk metrics, and recommendations",
        side_effects=[],
        reversible=True,
        requires_approval=False
    ),

    # Instead of get_market_data -> analyze_market_conditions
    "get_market_data": ActionTool(
        name="analyze_market_conditions",
        description="Analyze current market conditions for trading decisions",
        action_verb="analyze",
        parameters={"symbols": "list[str]", "timeframe": "str"},
        returns="MarketAnalysis with trend, volatility, and signals",
        side_effects=[],
        reversible=True,
        requires_approval=False
    ),

    # Instead of place_order -> execute_trade
    "place_order": ActionTool(
        name="execute_trade",
        description="Execute a trade with full risk validation",
        action_verb="execute",
        parameters={"symbol": "str", "side": "str", "quantity": "float"},
        returns="TradeResult with order_id, fill_price, status",
        side_effects=["modifies_portfolio", "incurs_commission"],
        reversible=True,  # Can close position
        requires_approval=True  # Goes through human checkpoint
    ),

    # Instead of get_account -> validate_trading_capacity
    "get_account": ActionTool(
        name="validate_trading_capacity",
        description="Validate account has capacity for proposed trade",
        action_verb="validate",
        parameters={"proposed_trade_value": "float"},
        returns="ValidationResult with available_funds, margin_status",
        side_effects=[],
        reversible=True,
        requires_approval=False
    ),
}


def get_recommended_tool_name(legacy_name: str) -> str:
    """Get the action-oriented tool name for a legacy getter."""
    mapping = ACTION_TOOL_MAPPINGS.get(legacy_name)
    if mapping:
        return mapping.name
    return legacy_name


# =============================================================================
# INTEGRATION HELPERS
# =============================================================================


def create_trading_checkpoint(context: dict[str, Any]) -> HumanCheckpoint:
    """Create a human checkpoint for a trading decision."""
    import uuid

    checkpoint_config = RiskCheckpoint()
    risk_level, reasons = checkpoint_config.assess_risk(context)

    return HumanCheckpoint(
        checkpoint_id=str(uuid.uuid4()),
        context=context,
        risk_level=risk_level,
        reasons=reasons
    )


def create_evaluator_optimizer_loop() -> EvaluatorOptimizerLoop:
    """Create a configured evaluator-optimizer loop for trading."""
    evaluator = TradingStrategyEvaluator(
        min_win_rate=0.55,
        min_sharpe=1.0,
        max_drawdown=0.10,
        min_trades=20
    )
    optimizer = TradingStrategyOptimizer()

    return EvaluatorOptimizerLoop(
        evaluator=evaluator,
        optimizer=optimizer,
        max_iterations=10,
        min_improvement=0.01
    )


# Global instances for easy access
error_recovery = ErrorRecoveryFramework()
