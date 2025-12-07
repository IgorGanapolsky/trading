"""
RL Evaluator-Optimizer Integration

Implements the Evaluator-Optimizer loop from Anthropic's patterns
specifically for the trading RL system.

This creates a continuous improvement cycle:
1. Run RL agent trades (paper or live)
2. Evaluate performance against criteria
3. Adjust RL parameters if not meeting targets
4. Loop until validation passes

Based on: https://www.anthropic.com/engineering/building-effective-agents
"""

import json
import logging
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from src.agents.anthropic_patterns import (
    EvaluationResult,
    EvaluatorOptimizerLoop,
    StrategyEvaluator,
    StrategyOptimizer,
)

logger = logging.getLogger(__name__)


@dataclass
class RLParameters:
    """RL agent tunable parameters."""

    # Signal thresholds
    entry_threshold: float = 0.6
    exit_threshold: float = 0.4
    min_confidence: float = 0.7

    # Position sizing
    max_position_pct: float = 0.10  # 10% max per position
    kelly_fraction: float = 0.25  # Kelly criterion fraction

    # Risk management
    stop_loss_pct: float = 0.02  # 2% stop loss
    take_profit_pct: float = 0.04  # 4% take profit
    max_daily_loss_pct: float = 0.02  # 2% max daily loss

    # Momentum parameters
    momentum_lookback: int = 20
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    rsi_period: int = 14
    rsi_oversold: int = 30
    rsi_overbought: int = 70

    # Volume filter
    volume_threshold: float = 1.5  # 1.5x average volume

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RLParameters":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class RLStrategyEvaluator(StrategyEvaluator):
    """
    Specialized evaluator for RL trading strategies.

    Evaluates against R&D phase goals:
    - Month 1: Break-even acceptable
    - Month 2: Win rate >55%, Sharpe >1.0
    - Month 3: Win rate >60%, Sharpe >1.5, $3-5/day profit
    """

    def __init__(self, phase: int = 1):
        """
        Initialize with current R&D phase.

        Args:
            phase: 1 (Month 1), 2 (Month 2), or 3 (Month 3)
        """
        self.phase = phase
        self._set_thresholds_for_phase()

    def _set_thresholds_for_phase(self):
        """Set evaluation thresholds based on R&D phase."""
        if self.phase == 1:
            # Month 1: Infrastructure - break-even acceptable
            self.min_win_rate = 0.45
            self.min_sharpe = 0.0
            self.max_drawdown = 0.15
            self.min_daily_profit = -5.0  # Allow small losses
        elif self.phase == 2:
            # Month 2: Building edge
            self.min_win_rate = 0.55
            self.min_sharpe = 1.0
            self.max_drawdown = 0.10
            self.min_daily_profit = 0.0
        else:
            # Month 3: Validation
            self.min_win_rate = 0.60
            self.min_sharpe = 1.5
            self.max_drawdown = 0.08
            self.min_daily_profit = 3.0

    def evaluate(self, context: dict[str, Any]) -> EvaluationResult:
        """Evaluate RL strategy against phase-specific goals."""
        trades = context.get("trades", [])
        win_rate = context.get("win_rate", 0)
        sharpe = context.get("sharpe_ratio", 0)
        max_dd = context.get("max_drawdown", 1.0)
        avg_daily_profit = context.get("avg_daily_profit", 0)
        total_pnl = context.get("total_pnl", 0)

        metrics = {
            "win_rate": win_rate,
            "sharpe_ratio": sharpe,
            "max_drawdown": max_dd,
            "avg_daily_profit": avg_daily_profit,
            "total_pnl": total_pnl,
            "trade_count": len(trades),
            "phase": self.phase,
        }

        feedback = []
        suggestions = []
        score = 0.0
        total_criteria = 4

        # 1. Win rate evaluation
        if win_rate >= self.min_win_rate:
            score += 1
            feedback.append(
                f"✓ Win rate {win_rate:.1%} meets Phase {self.phase} target "
                f"({self.min_win_rate:.0%})"
            )
        else:
            feedback.append(
                f"✗ Win rate {win_rate:.1%} below Phase {self.phase} target "
                f"({self.min_win_rate:.0%})"
            )
            suggestions.append(
                "Increase entry_threshold or min_confidence to filter weaker signals"
            )

        # 2. Sharpe ratio evaluation
        if sharpe >= self.min_sharpe:
            score += 1
            feedback.append(
                f"✓ Sharpe ratio {sharpe:.2f} meets Phase {self.phase} target ({self.min_sharpe})"
            )
        else:
            feedback.append(
                f"✗ Sharpe ratio {sharpe:.2f} below Phase {self.phase} target ({self.min_sharpe})"
            )
            suggestions.append(
                "Reduce max_position_pct or lower kelly_fraction for better risk-adjusted returns"
            )

        # 3. Drawdown evaluation
        if max_dd <= self.max_drawdown:
            score += 1
            feedback.append(
                f"✓ Max drawdown {max_dd:.1%} within Phase {self.phase} limit "
                f"({self.max_drawdown:.0%})"
            )
        else:
            feedback.append(
                f"✗ Max drawdown {max_dd:.1%} exceeds Phase {self.phase} limit "
                f"({self.max_drawdown:.0%})"
            )
            suggestions.append("Tighten stop_loss_pct or reduce max_daily_loss_pct")

        # 4. Daily profit evaluation
        if avg_daily_profit >= self.min_daily_profit:
            score += 1
            feedback.append(
                f"✓ Avg daily profit ${avg_daily_profit:.2f} meets Phase {self.phase} target "
                f"(${self.min_daily_profit:.2f})"
            )
        else:
            feedback.append(
                f"✗ Avg daily profit ${avg_daily_profit:.2f} below Phase {self.phase} target "
                f"(${self.min_daily_profit:.2f})"
            )
            suggestions.append(
                "Consider increasing take_profit_pct or adjusting momentum parameters"
            )

        # Normalize score
        normalized_score = score / total_criteria
        passed = normalized_score >= 0.75  # Need 3/4 criteria

        return EvaluationResult(
            score=normalized_score,
            metrics=metrics,
            feedback=feedback,
            suggestions=suggestions,
            passed=passed,
        )


class RLParameterOptimizer(StrategyOptimizer):
    """
    Optimizer for RL trading parameters.

    Uses evaluation feedback to make targeted adjustments.
    """

    def __init__(self, learning_rate: float = 0.1):
        """
        Args:
            learning_rate: How aggressively to adjust parameters (0.0-1.0)
        """
        self.learning_rate = learning_rate

    def optimize(
        self, evaluation: EvaluationResult, current_params: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate optimized RL parameters based on evaluation."""
        new_params = current_params.copy()
        metrics = evaluation.metrics
        lr = self.learning_rate

        # Adjust based on win rate
        if metrics.get("win_rate", 0) < 0.55:
            # Tighten entry criteria
            if "entry_threshold" in new_params:
                new_params["entry_threshold"] = min(
                    new_params["entry_threshold"] * (1 + 0.1 * lr), 0.9
                )
            if "min_confidence" in new_params:
                new_params["min_confidence"] = min(new_params["min_confidence"] + 0.05 * lr, 0.95)
            # Also consider volume filter
            if "volume_threshold" in new_params:
                new_params["volume_threshold"] *= 1 + 0.1 * lr

        # Adjust based on Sharpe ratio
        if metrics.get("sharpe_ratio", 0) < 1.0:
            # Reduce position sizes
            if "max_position_pct" in new_params:
                new_params["max_position_pct"] = max(
                    new_params["max_position_pct"] * (1 - 0.1 * lr),
                    0.02,  # Minimum 2%
                )
            if "kelly_fraction" in new_params:
                new_params["kelly_fraction"] = max(
                    new_params["kelly_fraction"] * (1 - 0.1 * lr),
                    0.1,  # Minimum 10%
                )

        # Adjust based on drawdown
        if metrics.get("max_drawdown", 0) > 0.10:
            # Tighten stop-losses
            if "stop_loss_pct" in new_params:
                new_params["stop_loss_pct"] = max(
                    new_params["stop_loss_pct"] * (1 - 0.15 * lr),
                    0.01,  # Minimum 1%
                )
            if "max_daily_loss_pct" in new_params:
                new_params["max_daily_loss_pct"] = max(
                    new_params["max_daily_loss_pct"] * (1 - 0.1 * lr),
                    0.01,  # Minimum 1%
                )

        # Adjust based on daily profit
        if metrics.get("avg_daily_profit", 0) < 3.0:
            # Try wider take profits (let winners run)
            if "take_profit_pct" in new_params:
                new_params["take_profit_pct"] = min(
                    new_params["take_profit_pct"] * (1 + 0.1 * lr),
                    0.10,  # Maximum 10%
                )

        return new_params


class RLEvaluatorOptimizer:
    """
    Main interface for running RL evaluation-optimization loops.

    Usage:
        evaluator = RLEvaluatorOptimizer(phase=2)
        optimized_params, result = await evaluator.run(
            initial_params=RLParameters(),
            get_performance_data=my_data_fetcher,
            save_params=my_param_saver
        )
    """

    def __init__(self, phase: int = 1, max_iterations: int = 10, learning_rate: float = 0.1):
        self.phase = phase
        self.evaluator = RLStrategyEvaluator(phase=phase)
        self.optimizer = RLParameterOptimizer(learning_rate=learning_rate)
        self.loop = EvaluatorOptimizerLoop(
            evaluator=self.evaluator,
            optimizer=self.optimizer,
            max_iterations=max_iterations,
            min_improvement=0.05,
        )
        self.params_file = Path("data/rl_parameters.json")
        self.history_file = Path("data/rl_optimization_history.json")

    def load_params(self) -> RLParameters:
        """Load current RL parameters from disk."""
        if self.params_file.exists():
            try:
                data = json.loads(self.params_file.read_text())
                return RLParameters.from_dict(data)
            except Exception as e:
                logger.warning(f"Failed to load RL params: {e}")
        return RLParameters()

    def save_params(self, params: dict[str, Any]):
        """Save RL parameters to disk."""
        self.params_file.parent.mkdir(parents=True, exist_ok=True)
        self.params_file.write_text(json.dumps(params, indent=2))
        logger.info(f"Saved optimized RL parameters to {self.params_file}")

    def save_history(self):
        """Save optimization history for analysis."""
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        report = self.loop.get_improvement_report()
        report["phase"] = self.phase
        report["timestamp"] = datetime.now().isoformat()

        # Append to history
        history = []
        if self.history_file.exists():
            try:
                history = json.loads(self.history_file.read_text())
            except Exception:
                pass

        history.append(report)
        self.history_file.write_text(json.dumps(history, indent=2))

    async def run(
        self,
        initial_params: RLParameters | None = None,
        get_performance_data: Callable[[], dict[str, Any]] | None = None,
    ) -> tuple[RLParameters, EvaluationResult]:
        """
        Run the full evaluation-optimization loop.

        Args:
            initial_params: Starting parameters (or load from disk)
            get_performance_data: Function that returns current performance metrics

        Returns:
            Tuple of (optimized RLParameters, final EvaluationResult)
        """
        if initial_params is None:
            initial_params = self.load_params()

        if get_performance_data is None:
            get_performance_data = self._default_performance_fetcher

        def execute_strategy(params: dict[str, Any]) -> dict[str, Any]:
            """Execute strategy and return performance context."""
            return get_performance_data()

        optimized_dict, final_eval = await self.loop.run_loop(
            initial_params=initial_params.to_dict(),
            execute_strategy=execute_strategy,
            save_params=self.save_params,
        )

        self.save_history()

        return RLParameters.from_dict(optimized_dict), final_eval

    def _default_performance_fetcher(self) -> dict[str, Any]:
        """Default implementation that reads from system state."""
        state_file = Path("data/system_state.json")
        if not state_file.exists():
            return {
                "trades": [],
                "win_rate": 0,
                "sharpe_ratio": 0,
                "max_drawdown": 0,
                "avg_daily_profit": 0,
                "total_pnl": 0,
            }

        try:
            state = json.loads(state_file.read_text())
            return {
                "trades": state.get("trades", []),
                "win_rate": state.get("win_rate", 0),
                "sharpe_ratio": state.get("sharpe_ratio", 0),
                "max_drawdown": state.get("max_drawdown", 0),
                "avg_daily_profit": state.get("avg_daily_profit", 0),
                "total_pnl": state.get("total_pnl", 0),
            }
        except Exception as e:
            logger.error(f"Failed to read system state: {e}")
            return {
                "trades": [],
                "win_rate": 0,
                "sharpe_ratio": 0,
                "max_drawdown": 0,
                "avg_daily_profit": 0,
                "total_pnl": 0,
            }

    def quick_evaluate(self) -> EvaluationResult:
        """Run a quick evaluation without optimization."""
        context = self._default_performance_fetcher()
        return self.evaluator.evaluate(context)

    def get_current_status(self) -> dict[str, Any]:
        """Get current RL system status with evaluation."""
        params = self.load_params()
        eval_result = self.quick_evaluate()

        return {
            "phase": self.phase,
            "parameters": params.to_dict(),
            "evaluation": {
                "score": eval_result.score,
                "passed": eval_result.passed,
                "metrics": eval_result.metrics,
                "feedback": eval_result.feedback,
                "suggestions": eval_result.suggestions,
            },
            "last_optimized": self._get_last_optimization_time(),
        }

    def _get_last_optimization_time(self) -> str | None:
        """Get timestamp of last optimization."""
        if not self.history_file.exists():
            return None
        try:
            history = json.loads(self.history_file.read_text())
            if history:
                return history[-1].get("timestamp")
        except Exception:
            pass
        return None


# Convenience function for quick evaluation
def evaluate_rl_strategy(phase: int = 1) -> dict[str, Any]:
    """
    Quick evaluation of current RL strategy.

    Returns dict with evaluation results and suggestions.
    """
    evaluator = RLEvaluatorOptimizer(phase=phase)
    return evaluator.get_current_status()


# Convenience function for running optimization
async def optimize_rl_strategy(
    phase: int = 1, max_iterations: int = 10
) -> tuple[RLParameters, EvaluationResult]:
    """
    Run full RL optimization loop.

    Returns optimized parameters and final evaluation.
    """
    evaluator = RLEvaluatorOptimizer(phase=phase, max_iterations=max_iterations)
    return await evaluator.run()
