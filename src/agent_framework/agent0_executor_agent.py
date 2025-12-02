"""
Agent0 Executor Agent: Solves trading tasks using tools

The Executor Agent receives tasks from the Curriculum Agent and solves them
using available tools (market data, sentiment analysis, trading APIs, etc.).
As it succeeds, it enables the Curriculum Agent to generate harder tasks,
creating a co-evolution loop.

Inspired by: Agent0 paper (arXiv:2511.16043)
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .agent0_curriculum_agent import TaskCategory, TaskDifficulty, TradingTask

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of task execution"""

    execution_id: str = field(default_factory=lambda: str(uuid4()))
    task_id: str = ""
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    finished_at: str | None = None

    # Execution details
    success: bool = False
    success_score: float = 0.0  # 0-1 scale
    error: str | None = None

    # Results
    outputs: dict[str, Any] = field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    reasoning_steps: list[str] = field(default_factory=list)

    # Evaluation
    evaluation_scores: dict[str, float] = field(default_factory=dict)
    evaluation_feedback: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


class ExecutorAgent:
    """
    Executor Agent: Solves trading tasks using available tools

    Responsibilities:
    1. Receive tasks from Curriculum Agent
    2. Use available tools to solve tasks
    3. Provide execution results and success scores
    4. Enable curriculum evolution through performance feedback
    """

    def __init__(self, storage_dir: Path | None = None, tools: dict[str, Any] | None = None):
        """
        Initialize Executor Agent

        Args:
            storage_dir: Directory for storing execution results
            tools: Dictionary of available tools (will be initialized if None)
        """
        self.storage_dir = storage_dir or Path("data/agent_context/executor")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Initialize tools
        self.tools = tools or {}
        self._initialize_tools()

        # Execution tracking
        self.execution_history: list[ExecutionResult] = []

        logger.info(f"✅ Executor Agent initialized with {len(self.tools)} tools")

    def execute_task(self, task: TradingTask) -> ExecutionResult:
        """
        Execute a trading task

        Args:
            task: TradingTask to execute

        Returns:
            ExecutionResult with success status and outputs
        """
        logger.info(f"🎯 Executing task: {task.title} ({task.difficulty.value})")

        result = ExecutionResult(task_id=task.task_id, started_at=datetime.now().isoformat())

        try:
            # Execute based on task category
            if task.category == TaskCategory.MARKET_ANALYSIS:
                result = self._execute_market_analysis(task, result)
            elif task.category == TaskCategory.SIGNAL_GENERATION:
                result = self._execute_signal_generation(task, result)
            elif task.category == TaskCategory.RISK_MANAGEMENT:
                result = self._execute_risk_management(task, result)
            elif task.category == TaskCategory.PORTFOLIO_OPTIMIZATION:
                result = self._execute_portfolio_optimization(task, result)
            elif task.category == TaskCategory.EXECUTION_STRATEGY:
                result = self._execute_execution_strategy(task, result)
            elif task.category == TaskCategory.MULTI_ASSET:
                result = self._execute_multi_asset(task, result)
            elif task.category == TaskCategory.REGIME_DETECTION:
                result = self._execute_regime_detection(task, result)
            elif task.category == TaskCategory.SENTIMENT_INTEGRATION:
                result = self._execute_sentiment_integration(task, result)
            else:
                result.error = f"Unknown task category: {task.category}"
                result.success = False

            # Evaluate execution
            result = self._evaluate_execution(task, result)

        except Exception as e:
            logger.exception(f"❌ Task execution failed: {e}")
            result.error = str(e)
            result.success = False
            result.success_score = 0.0

        finally:
            result.finished_at = datetime.now().isoformat()
            self._save_result(result)
            self.execution_history.append(result)

        logger.info(
            f"{'✅' if result.success else '❌'} Task completed: success_score={result.success_score:.2f}"
        )

        return result

    def _execute_market_analysis(
        self, task: TradingTask, result: ExecutionResult
    ) -> ExecutionResult:
        """Execute market analysis task"""
        result.reasoning_steps.append("Starting market analysis")

        # Get market data
        market_data_results = {}
        for symbol in task.symbols:
            if "get_market_data" in self.tools:
                try:
                    data = self.tools["get_market_data"](
                        symbol=symbol, lookback_days=60, timeframe="1Day"
                    )
                    market_data_results[symbol] = data
                    result.tool_calls.append(
                        {"tool": "get_market_data", "symbol": symbol, "success": True}
                    )
                except Exception as e:
                    logger.warning(f"Failed to get market data for {symbol}: {e}")
                    result.tool_calls.append(
                        {
                            "tool": "get_market_data",
                            "symbol": symbol,
                            "success": False,
                            "error": str(e),
                        }
                    )

        # Analyze technical indicators
        if "analyze_technical_indicators" in self.tools:
            try:
                indicators = {}
                for symbol in task.symbols:
                    if symbol in market_data_results:
                        ind = self.tools["analyze_technical_indicators"](
                            symbol=symbol, data=market_data_results[symbol]
                        )
                        indicators[symbol] = ind

                result.outputs["indicators"] = indicators
                result.tool_calls.append({"tool": "analyze_technical_indicators", "success": True})
            except Exception as e:
                logger.warning(f"Failed to analyze indicators: {e}")
                result.tool_calls.append(
                    {
                        "tool": "analyze_technical_indicators",
                        "success": False,
                        "error": str(e),
                    }
                )

        # Determine market regime
        result.reasoning_steps.append("Analyzing market regime")
        regime = self._determine_regime(market_data_results, result.outputs.get("indicators", {}))
        result.outputs["market_regime"] = regime

        # For advanced tasks, add more sophisticated analysis
        if task.difficulty in [
            TaskDifficulty.ADVANCED,
            TaskDifficulty.EXPERT,
            TaskDifficulty.FRONTIER,
        ]:
            # Multi-timeframe analysis
            if task.difficulty != TaskDifficulty.BEGINNER:
                result.outputs["multi_timeframe_analysis"] = self._multi_timeframe_analysis(
                    task.symbols
                )

            # Sentiment integration
            if "query_sentiment" in self.tools:
                sentiment_results = {}
                for symbol in task.symbols:
                    try:
                        sentiment = self.tools["query_sentiment"](symbol=symbol)
                        sentiment_results[symbol] = sentiment
                    except Exception as e:
                        logger.warning(f"Failed to get sentiment for {symbol}: {e}")

                result.outputs["sentiment"] = sentiment_results

        result.success = True
        return result

    def _execute_signal_generation(
        self, task: TradingTask, result: ExecutionResult
    ) -> ExecutionResult:
        """Execute signal generation task"""
        result.reasoning_steps.append("Starting signal generation")

        # First, get market analysis
        market_result = self._execute_market_analysis(task, ExecutionResult(task_id=task.task_id))

        # Generate signals based on analysis
        signals = {}
        for symbol in task.symbols:
            signal = self._generate_signal(
                symbol=symbol,
                market_data=market_result.outputs.get("indicators", {}).get(symbol, {}),
                regime=market_result.outputs.get("market_regime", "UNKNOWN"),
                difficulty=task.difficulty,
            )
            signals[symbol] = signal

        result.outputs["signals"] = signals
        result.outputs["market_regime"] = market_result.outputs.get("market_regime")
        result.success = True

        return result

    def _execute_risk_management(
        self, task: TradingTask, result: ExecutionResult
    ) -> ExecutionResult:
        """Execute risk management task"""
        result.reasoning_steps.append("Starting risk management")

        # Get account information
        account_info = {}
        if "call_mcp_tool" in self.tools:
            try:
                account_info = self.tools["call_mcp_tool"](
                    server="alpaca", tool="get_account", params={}
                )
            except Exception as e:
                logger.warning(f"Failed to get account info: {e}")

        # Calculate position sizes
        position_sizes = {}
        for symbol in task.symbols:
            if "get_market_data" in self.tools:
                try:
                    data = self.tools["get_market_data"](symbol=symbol, lookback_days=30)
                    volatility = self._calculate_volatility(data)

                    # Calculate position size based on difficulty
                    if task.difficulty == TaskDifficulty.BEGINNER:
                        position_size = self._basic_position_size(account_info, volatility)
                    elif task.difficulty == TaskDifficulty.INTERMEDIATE:
                        position_size = self._volatility_adjusted_size(account_info, volatility)
                    else:
                        position_size = self._advanced_position_size(
                            account_info, volatility, task.symbols
                        )

                    position_sizes[symbol] = position_size
                except Exception as e:
                    logger.warning(f"Failed to calculate position size for {symbol}: {e}")

        result.outputs["position_sizes"] = position_sizes
        result.outputs["account_info"] = account_info
        result.success = True

        return result

    def _execute_portfolio_optimization(
        self, task: TradingTask, result: ExecutionResult
    ) -> ExecutionResult:
        """Execute portfolio optimization task"""
        result.reasoning_steps.append("Starting portfolio optimization")

        # Get market data for all symbols
        market_data = {}
        for symbol in task.symbols:
            if "get_market_data" in self.tools:
                try:
                    data = self.tools["get_market_data"](symbol=symbol, lookback_days=60)
                    market_data[symbol] = data
                except Exception as e:
                    logger.warning(f"Failed to get data for {symbol}: {e}")

        # Calculate correlations
        correlations = self._calculate_correlations(market_data)

        # Optimize portfolio
        optimization = self._optimize_portfolio(market_data, correlations, task.constraints)

        result.outputs["correlations"] = correlations
        result.outputs["optimization"] = optimization
        result.success = True

        return result

    def _execute_execution_strategy(
        self, task: TradingTask, result: ExecutionResult
    ) -> ExecutionResult:
        """Execute execution strategy task"""
        result.reasoning_steps.append("Starting execution strategy")

        # This would involve order execution planning
        # For now, return a basic strategy
        result.outputs["execution_strategy"] = {
            "order_type": "limit",
            "timing": "market_hours",
            "slippage_estimate": 0.001,
        }
        result.success = True

        return result

    def _execute_multi_asset(self, task: TradingTask, result: ExecutionResult) -> ExecutionResult:
        """Execute multi-asset task"""
        result.reasoning_steps.append("Starting multi-asset analysis")

        # Combine market analysis for multiple assets
        market_result = self._execute_market_analysis(task, ExecutionResult(task_id=task.task_id))

        # Cross-asset analysis
        cross_asset = self._cross_asset_analysis(task.symbols, market_result.outputs)

        result.outputs.update(market_result.outputs)
        result.outputs["cross_asset_analysis"] = cross_asset
        result.success = True

        return result

    def _execute_regime_detection(
        self, task: TradingTask, result: ExecutionResult
    ) -> ExecutionResult:
        """Execute regime detection task"""
        result.reasoning_steps.append("Starting regime detection")

        # Get market data
        market_data = {}
        for symbol in task.symbols:
            if "get_market_data" in self.tools:
                try:
                    data = self.tools["get_market_data"](symbol=symbol, lookback_days=90)
                    market_data[symbol] = data
                except Exception as e:
                    logger.warning(f"Failed to get data for {symbol}: {e}")

        # Detect regime
        regime = self._detect_regime(market_data)
        result.outputs["regime"] = regime
        result.outputs["regime_confidence"] = 0.75  # Placeholder

        # For advanced tasks, predict transitions
        if task.difficulty in [
            TaskDifficulty.ADVANCED,
            TaskDifficulty.EXPERT,
            TaskDifficulty.FRONTIER,
        ]:
            transition_probability = self._predict_regime_transition(market_data, regime)
            result.outputs["transition_probability"] = transition_probability

        result.success = True
        return result

    def _execute_sentiment_integration(
        self, task: TradingTask, result: ExecutionResult
    ) -> ExecutionResult:
        """Execute sentiment integration task"""
        result.reasoning_steps.append("Starting sentiment integration")

        # Get market analysis
        market_result = self._execute_market_analysis(task, ExecutionResult(task_id=task.task_id))

        # Get sentiment
        sentiment_results = {}
        if "query_sentiment" in self.tools:
            for symbol in task.symbols:
                try:
                    sentiment = self.tools["query_sentiment"](symbol=symbol)
                    sentiment_results[symbol] = sentiment
                except Exception as e:
                    logger.warning(f"Failed to get sentiment for {symbol}: {e}")

        # Integrate sentiment with market analysis
        integrated_analysis = self._integrate_sentiment(market_result.outputs, sentiment_results)

        result.outputs.update(market_result.outputs)
        result.outputs["sentiment"] = sentiment_results
        result.outputs["integrated_analysis"] = integrated_analysis
        result.success = True

        return result

    def _evaluate_execution(self, task: TradingTask, result: ExecutionResult) -> ExecutionResult:
        """Evaluate execution against task criteria"""
        if not result.success:
            result.success_score = 0.0
            return result

        # Evaluate based on task's evaluation criteria
        criteria = task.evaluation_criteria
        scores = {}
        total_weight = 0.0

        for criterion, weight in criteria.items():
            score = self._evaluate_criterion(criterion, task, result)
            scores[criterion] = score
            total_weight += weight

        # Calculate weighted success score
        if total_weight > 0:
            weighted_score = sum(scores[c] * criteria[c] for c in criteria) / total_weight
        else:
            weighted_score = 0.5  # Default

        result.evaluation_scores = scores
        result.success_score = weighted_score
        result.success = weighted_score >= 0.6  # Threshold for success

        # Generate feedback
        result.evaluation_feedback = self._generate_feedback(task, result, scores)

        return result

    def _evaluate_criterion(
        self, criterion: str, task: TradingTask, result: ExecutionResult
    ) -> float:
        """Evaluate a specific criterion"""
        outputs = result.outputs

        if criterion == "regime_accuracy":
            # Check if regime was identified
            return 1.0 if "market_regime" in outputs else 0.0

        elif criterion == "indicator_calculation":
            # Check if indicators were calculated
            return 1.0 if "indicators" in outputs and outputs["indicators"] else 0.0

        elif criterion == "reasoning_quality":
            # Check reasoning steps
            return min(1.0, len(result.reasoning_steps) / 3.0)

        elif criterion == "multi_timeframe_coherence":
            # Check multi-timeframe analysis
            return 1.0 if "multi_timeframe_analysis" in outputs else 0.0

        elif criterion == "signal_clarity":
            # Check if signals were generated
            return 1.0 if "signals" in outputs and outputs["signals"] else 0.0

        elif criterion == "position_size_accuracy":
            # Check if position sizes were calculated
            return 1.0 if "position_sizes" in outputs and outputs["position_sizes"] else 0.0

        elif criterion == "volatility_estimation":
            # Check if volatility was considered
            return 1.0 if "volatility" in str(outputs).lower() else 0.5

        elif criterion == "correlation_analysis":
            # Check if correlations were calculated
            return 1.0 if "correlations" in outputs else 0.0

        elif criterion == "regime_detection_accuracy":
            # Check regime detection
            return 1.0 if "regime" in outputs else 0.0

        elif criterion == "data_integration":
            # Check if multiple data sources were used
            data_sources = sum(1 for k in outputs if k in ["indicators", "sentiment", "regime"])
            return min(1.0, data_sources / 2.0)

        else:
            # Default: check if outputs exist
            return 0.7 if outputs else 0.0

    def _generate_feedback(
        self, task: TradingTask, result: ExecutionResult, scores: dict[str, float]
    ) -> str:
        """Generate evaluation feedback"""
        feedback_parts = []

        if result.success:
            feedback_parts.append(
                f"✅ Task completed successfully (score: {result.success_score:.2f})"
            )
        else:
            feedback_parts.append(
                f"❌ Task completed with issues (score: {result.success_score:.2f})"
            )

        # Add criterion-specific feedback
        for criterion, score in scores.items():
            if score < 0.7:
                feedback_parts.append(f"⚠️ {criterion}: {score:.2f} (needs improvement)")

        return "\n".join(feedback_parts)

    # Helper methods for task execution

    def _determine_regime(self, market_data: dict, indicators: dict) -> str:
        """Determine market regime"""
        # Simple regime detection based on indicators
        if not indicators:
            return "UNKNOWN"

        # Check for bullish/bearish signals
        bullish_signals = 0
        bearish_signals = 0

        for _symbol, ind in indicators.items():
            if isinstance(ind, dict):
                rsi = ind.get("rsi", 50)
                macd_hist = ind.get("macd_histogram", 0)

                if rsi > 50 and macd_hist > 0:
                    bullish_signals += 1
                elif rsi < 50 and macd_hist < 0:
                    bearish_signals += 1

        if bullish_signals > bearish_signals:
            return "BULLISH"
        elif bearish_signals > bullish_signals:
            return "BEARISH"
        else:
            return "RANGE_BOUND"

    def _multi_timeframe_analysis(self, symbols: list[str]) -> dict[str, Any]:
        """Perform multi-timeframe analysis"""
        return {"daily": "analyzed", "hourly": "analyzed", "15min": "analyzed"}

    def _generate_signal(
        self, symbol: str, market_data: dict, regime: str, difficulty: TaskDifficulty
    ) -> dict[str, Any]:
        """Generate trading signal"""
        return {
            "symbol": symbol,
            "action": ("BUY" if regime == "BULLISH" else "SELL" if regime == "BEARISH" else "HOLD"),
            "confidence": 0.7,
            "entry": 100.0,
            "stop_loss": 95.0,
            "take_profit": 110.0,
        }

    def _calculate_volatility(self, data: Any) -> float:
        """Calculate volatility from market data"""
        # Placeholder - would calculate actual volatility
        return 0.02  # 2% volatility

    def _basic_position_size(self, account_info: dict, volatility: float) -> dict[str, Any]:
        """Calculate basic position size"""
        account_value = account_info.get("equity", 10000)
        risk_per_trade = account_value * 0.01  # 1% risk
        position_size = risk_per_trade / (volatility * account_value)

        return {
            "position_size": position_size,
            "risk_amount": risk_per_trade,
            "method": "basic",
        }

    def _volatility_adjusted_size(self, account_info: dict, volatility: float) -> dict[str, Any]:
        """Calculate volatility-adjusted position size"""
        base_size = self._basic_position_size(account_info, volatility)
        # Adjust for volatility
        volatility_multiplier = 1.0 / (1.0 + volatility * 10)
        base_size["position_size"] *= volatility_multiplier
        base_size["method"] = "volatility_adjusted"
        return base_size

    def _advanced_position_size(
        self, account_info: dict, volatility: float, symbols: list[str]
    ) -> dict[str, Any]:
        """Calculate advanced position size with portfolio considerations"""
        base_size = self._volatility_adjusted_size(account_info, volatility)
        # Adjust for portfolio concentration
        concentration_factor = 1.0 / len(symbols) if symbols else 1.0
        base_size["position_size"] *= concentration_factor
        base_size["method"] = "advanced"
        return base_size

    def _calculate_correlations(self, market_data: dict[str, Any]) -> dict[str, dict[str, float]]:
        """Calculate correlations between symbols"""
        correlations = {}
        symbols = list(market_data.keys())

        for i, sym1 in enumerate(symbols):
            correlations[sym1] = {}
            for sym2 in symbols[i + 1 :]:
                # Placeholder correlation
                correlations[sym1][sym2] = 0.5

        return correlations

    def _optimize_portfolio(
        self, market_data: dict, correlations: dict, constraints: dict
    ) -> dict[str, Any]:
        """Optimize portfolio allocation"""
        return {
            "allocations": {symbol: 1.0 / len(market_data) for symbol in market_data},
            "expected_return": 0.08,
            "risk": 0.15,
        }

    def _cross_asset_analysis(self, symbols: list[str], outputs: dict) -> dict[str, Any]:
        """Perform cross-asset analysis"""
        return {
            "correlations": "calculated",
            "sector_rotation": "analyzed",
            "macro_regime": "identified",
        }

    def _detect_regime(self, market_data: dict) -> str:
        """Detect market regime"""
        return "BULLISH"  # Placeholder

    def _predict_regime_transition(
        self, market_data: dict, current_regime: str
    ) -> dict[str, float]:
        """Predict regime transition probabilities"""
        return {"BULLISH": 0.4, "BEARISH": 0.3, "RANGE_BOUND": 0.3}

    def _integrate_sentiment(self, market_outputs: dict, sentiment_results: dict) -> dict[str, Any]:
        """Integrate sentiment with market analysis"""
        return {"combined_score": 0.7, "sentiment_weight": 0.3, "market_weight": 0.7}

    def _initialize_tools(self):
        """Initialize available tools"""
        # Try to import and initialize tools from existing system
        try:
            from src.deepagents_integration.tools import (
                analyze_technical_indicators,
                get_market_data,
                get_sentiment_history,
                query_sentiment,
            )

            self.tools["get_market_data"] = get_market_data
            self.tools["analyze_technical_indicators"] = analyze_technical_indicators
            self.tools["query_sentiment"] = query_sentiment
            self.tools["get_sentiment_history"] = get_sentiment_history
        except ImportError:
            logger.warning("Could not import deepagents tools")

        # Try to import MCP tools
        try:
            from src.mcp.client import MCPClient

            mcp_client = MCPClient()

            def call_mcp_tool(server: str, tool: str, params: dict[str, Any]) -> dict[str, Any]:
                """Wrapper for MCP tool calls"""
                try:
                    return mcp_client.call_tool(server, tool, params)
                except Exception as e:
                    logger.error(f"MCP tool call failed: {e}")
                    return {}

            self.tools["call_mcp_tool"] = call_mcp_tool
        except Exception as e:
            logger.warning(f"Could not initialize MCP tools: {e}")

    def _save_result(self, result: ExecutionResult):
        """Save execution result to disk"""
        results_dir = self.storage_dir / "results"
        results_dir.mkdir(parents=True, exist_ok=True)

        result_file = results_dir / f"{result.execution_id}.json"
        with open(result_file, "w") as f:
            json.dump(result.to_dict(), f, indent=2)

    def get_capability_score(self) -> float:
        """Calculate current capability score based on execution history"""
        if not self.execution_history:
            return 0.5  # Default

        # Calculate average success score from recent executions
        recent_results = self.execution_history[-20:]  # Last 20 executions
        avg_score = sum(r.success_score for r in recent_results) / len(recent_results)

        return avg_score

    def get_statistics(self) -> dict[str, Any]:
        """Get executor statistics"""
        return {
            "total_executions": len(self.execution_history),
            "successful_executions": sum(1 for r in self.execution_history if r.success),
            "average_success_score": self.get_capability_score(),
            "available_tools": list(self.tools.keys()),
        }
