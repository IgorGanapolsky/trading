"""
Executor Agent: Solves trading tasks using external tools

Inspired by Agent0's Executor Agent pattern:
- Receives tasks from Curriculum Agent
- Uses tool-integrated reasoning to solve them
- Learns from successes and failures
- Improves capabilities over time
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .base import AgentResult, TradingAgent
from .context import RunContext
from .curriculum_agent import TaskPerformance, TradingTask

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Result from a tool execution"""

    tool_name: str
    success: bool
    result: Any
    execution_time_ms: float
    error: str | None = None


@dataclass
class TaskSolution:
    """Solution to a trading task"""

    task_id: str
    executor_agent: str
    solution: dict[str, Any]
    tool_results: list[ToolResult] = field(default_factory=list)
    reasoning: str = ""
    confidence: float = 0.0
    completed_at: str = field(default_factory=lambda: datetime.now().isoformat())


class ExecutorAgent(TradingAgent):
    """
    Executor Agent: Solves trading tasks using external tools.

    Key Responsibilities:
    1. Receive tasks from Curriculum Agent
    2. Use tool-integrated reasoning to solve them
    3. Learn from successes and failures
    4. Improve capabilities over time
    """

    def __init__(self, storage_dir: Path | None = None, curriculum_agent: Any | None = None):
        super().__init__("ExecutorAgent")
        self.storage_dir = storage_dir or Path("data/agent_context/executor")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.curriculum_agent = curriculum_agent

        # Tool registry
        self.available_tools: dict[str, Any] = {}
        self.tool_usage_stats: dict[str, dict[str, int]] = {}

        # Solution history
        self.solutions: dict[str, TaskSolution] = {}

        # Learning state
        self.learned_patterns: list[dict[str, Any]] = []

        # Deep Q-Network for learning (optional)
        self.dqn_agent = None
        self.use_dqn = os.getenv("EXECUTOR_USE_DQN", "false").lower() == "true"
        if self.use_dqn:
            try:
                from src.ml.dqn_agent import DQNAgent
                from src.ml.multi_step_learning import NStepDQNAgent

                # State dimension based on task features
                state_dim = 20  # Task features: difficulty, category, objectives count, etc.
                dqn = DQNAgent(
                    state_dim=state_dim,
                    action_dim=len(self.available_tools) if self.available_tools else 3,
                    use_dueling=True,
                    use_double=True,
                    use_prioritized_replay=True,
                )
                self.dqn_agent = NStepDQNAgent(dqn, n=3)
                logger.info("✅ Executor Agent DQN initialized")
            except Exception as e:
                logger.warning(f"⚠️ Executor Agent DQN unavailable: {e}")

        # Initialize tools
        self._initialize_tools()

        logger.info(f"✅ Executor Agent initialized: {len(self.available_tools)} tools available")

    def execute(self, context: RunContext) -> AgentResult:
        """
        Execute a trading task.

        Args:
            context: Run context containing the task to execute

        Returns:
            AgentResult with solution and performance metrics
        """
        try:
            # Extract task from context (check both config.data and state_cache)
            task_data = context.config.data.get("task") or context.state_cache.get("task")
            if not task_data:
                return AgentResult(
                    name=self.agent_name,
                    succeeded=False,
                    error="No task provided in context",
                )

            task = TradingTask.from_dict(task_data)

            # Solve the task
            start_time = time.time()
            solution = self._solve_task(task, context)
            execution_time = time.time() - start_time

            # Store solution
            self.solutions[solution.task_id] = solution
            self._save_solution(solution)

            # Evaluate performance
            performance = self._evaluate_performance(task, solution, execution_time)

            # Record performance with curriculum agent
            if self.curriculum_agent:
                self.curriculum_agent.record_performance(performance)

            # Learn from experience
            self._learn_from_experience(task, solution, performance)

            logger.info(
                f"✅ Task solved: {task.task_id} "
                f"(success={performance.success}, quality={performance.quality_score:.2f})"
            )

            return AgentResult(
                name=self.agent_name,
                succeeded=performance.success,
                payload={
                    "solution": asdict(solution),
                    "performance": asdict(performance),
                    "execution_time_seconds": execution_time,
                },
            )

        except Exception as e:
            logger.exception(f"❌ Executor Agent failed: {e}")
            return AgentResult(name=self.agent_name, succeeded=False, error=str(e))

    def _solve_task(self, task: TradingTask, context: RunContext) -> TaskSolution:
        """
        Solve a trading task using tool-integrated reasoning.

        Strategy:
        1. Analyze task requirements
        2. Select appropriate tools
        3. Execute tools in sequence/parallel
        4. Synthesize results into solution
        """
        tool_results: list[ToolResult] = []
        solution_data: dict[str, Any] = {}
        reasoning_parts: list[str] = []

        # Step 1: Analyze task
        reasoning_parts.append(f"Analyzing task: {task.description}")
        reasoning_parts.append(f"Objectives: {', '.join(task.objectives)}")
        reasoning_parts.append(f"Required tools: {', '.join(task.required_tools)}")

        # Step 2: Execute required tools
        for tool_name in task.required_tools:
            if tool_name in self.available_tools:
                tool_result = self._execute_tool(tool_name, task, context)
                tool_results.append(tool_result)

                if tool_result.success:
                    reasoning_parts.append(f"✅ {tool_name}: {str(tool_result.result)[:100]}")
                    solution_data[tool_name] = tool_result.result
                else:
                    reasoning_parts.append(f"❌ {tool_name} failed: {tool_result.error}")
            else:
                reasoning_parts.append(f"⚠️ Tool {tool_name} not available")
                tool_results.append(
                    ToolResult(
                        tool_name=tool_name,
                        success=False,
                        result=None,
                        execution_time_ms=0.0,
                        error=f"Tool {tool_name} not available",
                    )
                )

        # Step 3: Synthesize solution
        solution = self._synthesize_solution(task, tool_results, solution_data)

        # Step 4: Calculate confidence
        confidence = self._calculate_confidence(task, tool_results, solution)

        return TaskSolution(
            task_id=task.task_id,
            executor_agent=self.agent_name,
            solution=solution,
            tool_results=tool_results,
            reasoning="\n".join(reasoning_parts),
            confidence=confidence,
        )

    def _execute_tool(self, tool_name: str, task: TradingTask, context: RunContext) -> ToolResult:
        """Execute a specific tool"""
        start_time = time.time()

        try:
            tool = self.available_tools.get(tool_name)
            if not tool:
                return ToolResult(
                    tool_name=tool_name,
                    success=False,
                    result=None,
                    execution_time_ms=0.0,
                    error=f"Tool {tool_name} not found",
                )

            # Execute tool with task context
            result = tool(task=task, context=context)

            execution_time = (time.time() - start_time) * 1000

            # Update usage stats
            if tool_name not in self.tool_usage_stats:
                self.tool_usage_stats[tool_name] = {"success": 0, "failure": 0}
            self.tool_usage_stats[tool_name]["success"] += 1

            # Learn from experience if DQN enabled
            if self.dqn_agent:
                self._learn_tool_selection(task, tool_name, True, result)

            return ToolResult(
                tool_name=tool_name,
                success=True,
                result=result,
                execution_time_ms=execution_time,
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000

            # Update usage stats
            if tool_name not in self.tool_usage_stats:
                self.tool_usage_stats[tool_name] = {"success": 0, "failure": 0}
            self.tool_usage_stats[tool_name]["failure"] += 1

            # Learn from failure if DQN enabled
            if self.dqn_agent:
                self._learn_tool_selection(task, tool_name, False, None)

            logger.error(f"Tool {tool_name} failed: {e}")
            return ToolResult(
                tool_name=tool_name,
                success=False,
                result=None,
                execution_time_ms=execution_time,
                error=str(e),
            )

    def _synthesize_solution(
        self,
        task: TradingTask,
        tool_results: list[ToolResult],
        solution_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Synthesize tool results into a complete solution.

        This is where the agent combines multiple tool outputs
        to create a coherent solution to the task.
        """
        solution: dict[str, Any] = {
            "task_id": task.task_id,
            "category": task.category.value,
            "objectives_met": [],
            "results": solution_data,
            "recommendations": [],
        }

        # Check which objectives were met
        successful_tools = {r.tool_name for r in tool_results if r.success}

        # Map tools to objectives
        for objective in task.objectives:
            # Simple heuristic: if required tools succeeded, objective is met
            required_for_objective = self._get_tools_for_objective(objective, task)
            if required_for_objective.issubset(successful_tools):
                solution["objectives_met"].append(objective)

        # Generate recommendations based on task category
        if task.category.value == "market_analysis":
            solution["recommendations"] = self._generate_market_recommendations(solution_data)
        elif task.category.value == "risk_management":
            solution["recommendations"] = self._generate_risk_recommendations(solution_data)
        elif task.category.value == "execution_optimization":
            solution["recommendations"] = self._generate_execution_recommendations(solution_data)
        else:
            solution["recommendations"] = ["Task completed"]

        return solution

    def _get_tools_for_objective(self, objective: str, task: TradingTask) -> set[str]:
        """Determine which tools are needed for an objective"""
        # Simple heuristic: all required tools are needed
        return set(task.required_tools)

    def _generate_market_recommendations(self, solution_data: dict[str, Any]) -> list[str]:
        """Generate trading recommendations from market analysis"""
        recommendations = []

        if "technical_indicators" in solution_data:
            indicators = solution_data["technical_indicators"]
            if isinstance(indicators, dict):
                if indicators.get("macd_bullish"):
                    recommendations.append("BUY signal: MACD bullish crossover")
                if indicators.get("rsi_oversold"):
                    recommendations.append("BUY signal: RSI oversold")
                if indicators.get("rsi_overbought"):
                    recommendations.append("SELL signal: RSI overbought")

        if not recommendations:
            recommendations.append("HOLD: No clear signal")

        return recommendations

    def _generate_risk_recommendations(self, solution_data: dict[str, Any]) -> list[str]:
        """Generate risk management recommendations"""
        recommendations = []

        if "position_size" in solution_data:
            size = solution_data["position_size"]
            recommendations.append(f"Recommended position size: ${size:.2f}")

        if "risk_metrics" in solution_data:
            metrics = solution_data["risk_metrics"]
            if isinstance(metrics, dict) and metrics.get("portfolio_risk") > 0.02:
                recommendations.append("WARNING: Portfolio risk exceeds 2% limit")

        return recommendations

    def _generate_execution_recommendations(self, solution_data: dict[str, Any]) -> list[str]:
        """Generate execution optimization recommendations"""
        recommendations = []

        if "execution_method" in solution_data:
            method = solution_data["execution_method"]
            recommendations.append(f"Recommended execution: {method}")

        if "expected_slippage" in solution_data:
            slippage = solution_data["expected_slippage"]
            recommendations.append(f"Expected slippage: {slippage:.4f}")

        return recommendations

    def _calculate_confidence(
        self,
        task: TradingTask,
        tool_results: list[ToolResult],
        solution: dict[str, Any],
    ) -> float:
        """
        Calculate confidence score for the solution.

        Factors:
        - Tool success rate
        - Objectives met
        - Solution completeness
        """
        if not tool_results:
            return 0.0

        # Tool success rate
        successful_tools = sum(1 for r in tool_results if r.success)
        tool_confidence = successful_tools / len(tool_results)

        # Objectives met
        objectives_met = len(solution.get("objectives_met", []))
        objectives_total = len(task.objectives)
        objective_confidence = objectives_met / objectives_total if objectives_total > 0 else 0.0

        # Combined confidence
        confidence = tool_confidence * 0.6 + objective_confidence * 0.4

        return min(confidence, 1.0)

    def _evaluate_performance(
        self, task: TradingTask, solution: TaskSolution, execution_time: float
    ) -> TaskPerformance:
        """
        Evaluate performance on the task.

        Success criteria:
        - All required tools executed successfully
        - Most objectives met
        - Solution is complete and actionable
        """
        # Check tool success
        tool_success_rate = (
            sum(1 for r in solution.tool_results if r.success) / len(solution.tool_results)
            if solution.tool_results
            else 0.0
        )

        # Check objectives met
        objectives_met = len(solution.solution.get("objectives_met", []))
        objectives_total = len(task.objectives)
        objective_rate = objectives_met / objectives_total if objectives_total > 0 else 0.0

        # Determine success
        success = tool_success_rate > 0.7 and objective_rate > 0.6

        # Calculate quality score
        quality_score = tool_success_rate * 0.5 + objective_rate * 0.5

        # Collect errors
        errors = [r.error for r in solution.tool_results if not r.success and r.error]

        # Generate feedback
        feedback = self._generate_feedback(task, solution, success, quality_score)

        return TaskPerformance(
            task_id=task.task_id,
            executor_agent=self.agent_name,
            success=success,
            completion_time_seconds=execution_time,
            quality_score=quality_score,
            tool_usage={r.tool_name: 1 for r in solution.tool_results},
            errors=errors,
            feedback=feedback,
        )

    def _generate_feedback(
        self,
        task: TradingTask,
        solution: TaskSolution,
        success: bool,
        quality_score: float,
    ) -> str:
        """Generate feedback on task execution"""
        if success:
            return (
                f"Successfully completed {task.category.value} task. "
                f"Quality score: {quality_score:.2f}. "
                f"All critical objectives met."
            )
        else:
            return (
                f"Partially completed {task.category.value} task. "
                f"Quality score: {quality_score:.2f}. "
                f"Some objectives not met. Review tool execution."
            )

    def _learn_from_experience(
        self, task: TradingTask, solution: TaskSolution, performance: TaskPerformance
    ) -> None:
        """Learn patterns from task execution"""
        pattern = {
            "task_category": task.category.value,
            "difficulty": task.difficulty.value,
            "tools_used": [r.tool_name for r in solution.tool_results],
            "success": performance.success,
            "quality_score": performance.quality_score,
            "learned_at": datetime.now().isoformat(),
        }

        self.learned_patterns.append(pattern)

        # Keep only recent patterns (last 100)
        if len(self.learned_patterns) > 100:
            self.learned_patterns = self.learned_patterns[-100:]

        logger.debug(f"📚 Learned pattern: {pattern}")

    def _initialize_tools(self) -> None:
        """Initialize available tools"""
        # Market data tools
        self.available_tools["market_data"] = self._tool_market_data
        self.available_tools["technical_indicators"] = self._tool_technical_indicators
        self.available_tools["multi_timeframe"] = self._tool_multi_timeframe

        # Risk tools
        self.available_tools["risk_calculator"] = self._tool_risk_calculator
        self.available_tools["position_sizer"] = self._tool_position_sizer
        self.available_tools["portfolio_analyzer"] = self._tool_portfolio_analyzer

        # Analysis tools
        self.available_tools["correlation_calculator"] = self._tool_correlation_calculator
        self.available_tools["regime_detector"] = self._tool_regime_detector
        self.available_tools["statistical_analysis"] = self._tool_statistical_analysis

        # Execution tools
        self.available_tools["execution_analyzer"] = self._tool_execution_analyzer
        self.available_tools["slippage_calculator"] = self._tool_slippage_calculator

        # Sentiment tools
        self.available_tools["sentiment_analyzer"] = self._tool_sentiment_analyzer
        self.available_tools["news_fetcher"] = self._tool_news_fetcher

        # Other tools
        self.available_tools["pattern_detector"] = self._tool_pattern_detector
        self.available_tools["stress_tester"] = self._tool_stress_tester
        self.available_tools["portfolio_optimizer"] = self._tool_portfolio_optimizer

    # Tool implementations (simplified - would integrate with actual systems)

    def _tool_market_data(self, task: TradingTask, context: RunContext) -> dict[str, Any]:
        """Fetch market data"""
        symbols = task.context.get("symbols", ["SPY"])
        return {
            "symbols": symbols,
            "data_available": True,
            "timestamp": datetime.now().isoformat(),
        }

    def _tool_technical_indicators(self, task: TradingTask, context: RunContext) -> dict[str, Any]:
        """Calculate technical indicators"""
        return {
            "macd_bullish": True,
            "rsi": 45.0,
            "rsi_oversold": False,
            "rsi_overbought": False,
        }

    def _tool_multi_timeframe(self, task: TradingTask, context: RunContext) -> dict[str, Any]:
        """Multi-timeframe analysis"""
        return {"timeframes": ["1h", "4h", "daily"], "alignment": "bullish"}

    def _tool_risk_calculator(self, task: TradingTask, context: RunContext) -> dict[str, Any]:
        """Calculate risk metrics"""
        return {"portfolio_risk": 0.015, "position_risk": 0.01, "max_loss": 0.02}

    def _tool_position_sizer(self, task: TradingTask, context: RunContext) -> dict[str, Any]:
        """Calculate position size"""
        return {
            "position_size": 100.0,
            "kelly_fraction": 0.25,
            "volatility_adjusted": True,
        }

    def _tool_portfolio_analyzer(self, task: TradingTask, context: RunContext) -> dict[str, Any]:
        """Analyze portfolio"""
        return {"positions": 3, "total_value": 1000.0, "diversification_score": 0.7}

    def _tool_correlation_calculator(
        self, task: TradingTask, context: RunContext
    ) -> dict[str, Any]:
        """Calculate correlations"""
        return {"correlation_matrix": {}, "avg_correlation": 0.5}

    def _tool_regime_detector(self, task: TradingTask, context: RunContext) -> dict[str, Any]:
        """Detect market regime"""
        return {"regime": "bull", "confidence": 0.75}

    def _tool_statistical_analysis(self, task: TradingTask, context: RunContext) -> dict[str, Any]:
        """Statistical analysis"""
        return {"volatility": 0.2, "mean_return": 0.001, "sharpe_ratio": 1.5}

    def _tool_execution_analyzer(self, task: TradingTask, context: RunContext) -> dict[str, Any]:
        """Analyze execution"""
        return {"execution_method": "limit", "optimal_timing": "market_open"}

    def _tool_slippage_calculator(self, task: TradingTask, context: RunContext) -> dict[str, Any]:
        """Calculate slippage"""
        return {"expected_slippage": 0.0001, "spread": 0.0002}

    def _tool_sentiment_analyzer(self, task: TradingTask, context: RunContext) -> dict[str, Any]:
        """Analyze sentiment"""
        return {"sentiment_score": 0.6, "sources": ["news", "social"]}

    def _tool_news_fetcher(self, task: TradingTask, context: RunContext) -> dict[str, Any]:
        """Fetch news"""
        return {"articles": [], "sentiment": "neutral"}

    def _tool_pattern_detector(self, task: TradingTask, context: RunContext) -> dict[str, Any]:
        """Detect patterns"""
        return {"pattern": "continuation", "confidence": 0.7}

    def _tool_stress_tester(self, task: TradingTask, context: RunContext) -> dict[str, Any]:
        """Stress testing"""
        return {"max_drawdown": 0.05, "stress_scenarios": []}

    def _tool_portfolio_optimizer(self, task: TradingTask, context: RunContext) -> dict[str, Any]:
        """Optimize portfolio"""
        return {"optimal_weights": {}, "expected_return": 0.001, "risk": 0.015}

    def _learn_tool_selection(self, task: TradingTask, tool_name: str, success: bool, result: Any):
        """Learn optimal tool selection using DQN."""
        if not self.dqn_agent:
            return

        try:
            # Extract state features from task
            state = self._extract_task_features(task)

            # Map tool name to action index
            tool_list = list(self.available_tools.keys())
            if tool_name not in tool_list:
                return

            action_idx = tool_list.index(tool_name)

            # Calculate reward based on success and result quality
            reward = 1.0 if success else -0.5
            if success and result:
                # Additional reward based on result quality
                if isinstance(result, dict):
                    if result.get("quality_score", 0) > 0.7:
                        reward += 0.3

            # Create next state (same for now, could be improved)
            next_state = state.copy()

            # Store transition
            self.dqn_agent.store_transition(
                state=state,
                action=action_idx,
                reward=reward,
                next_state=next_state,
                done=False,
            )

            # Train periodically
            if len(self.dqn_agent.base_agent.replay_buffer) > 100:
                self.dqn_agent.train_step()

        except Exception as e:
            logger.warning(f"Failed to learn tool selection: {e}")

    def _extract_task_features(self, task: TradingTask):
        """Extract feature vector from task for DQN."""
        import numpy as np

        # Feature engineering: encode task properties
        features = []

        # Difficulty (one-hot encoded)
        difficulty_map = {"easy": 0, "medium": 1, "hard": 2, "frontier": 3}
        difficulty_onehot = [0.0] * 4
        difficulty_onehot[difficulty_map.get(task.difficulty.value, 1)] = 1.0
        features.extend(difficulty_onehot)

        # Category (one-hot encoded)
        category_map = {
            "market_analysis": 0,
            "risk_management": 1,
            "execution_optimization": 2,
            "portfolio_optimization": 3,
            "regime_detection": 4,
            "sentiment_integration": 5,
            "multi_timeframe": 6,
            "edge_case": 7,
        }
        category_onehot = [0.0] * 8
        category_onehot[category_map.get(task.category.value, 0)] = 1.0
        features.extend(category_onehot)

        # Objectives count (normalized)
        features.append(min(len(task.objectives) / 10.0, 1.0))

        # Required tools count (normalized)
        features.append(min(len(task.required_tools) / 5.0, 1.0))

        # Expected capabilities count (normalized)
        features.append(min(len(task.expected_capabilities) / 5.0, 1.0))

        # Pad or truncate to fixed size
        target_size = 20
        if len(features) < target_size:
            features.extend([0.0] * (target_size - len(features)))
        else:
            features = features[:target_size]

        return np.array(features, dtype=np.float32)

    def _save_solution(self, solution: TaskSolution) -> None:
        """Save solution to disk"""
        solution_file = self.storage_dir / "solutions" / f"{solution.task_id}.json"
        solution_file.parent.mkdir(parents=True, exist_ok=True)

        with open(solution_file, "w") as f:
            json.dump(asdict(solution), f, indent=2, default=str)
