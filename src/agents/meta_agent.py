"""
Meta-Agent: Hierarchical coordinator inspired by Hi-DARTS

Responsibilities:
- Analyze market volatility and regime
- Coordinate Research, Signal, Risk, and Execution agents
- Adapt strategy based on market conditions
- Learn which agents to trust in different market states
"""

import logging
from typing import Any

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class MetaAgent(BaseAgent):
    """
    Meta-Agent coordinates all other agents based on market conditions.

    Inspired by Hi-DARTS hierarchical framework:
    - Detects market volatility
    - Activates appropriate specialist agents
    - Balances exploration vs exploitation
    """

    def __init__(self):
        super().__init__(
            name="MetaAgent", role="Hierarchical coordinator and market regime detector"
        )
        self.agents: dict[str, BaseAgent] = {}
        self.market_regime = "UNKNOWN"  # LOW_VOL, HIGH_VOL, TRENDING, RANGING

    def register_agent(self, agent: BaseAgent) -> None:
        """Register a specialist agent."""
        self.agents[agent.name] = agent
        logger.info(f"MetaAgent registered: {agent.name}")

    def analyze(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Coordinate all agents to make trading decision.

        Args:
            data: Market data, news, portfolio state

        Returns:
            Coordinated trading decision
        """
        # Step 1: Detect market regime
        regime = self._detect_market_regime(data)
        self.market_regime = regime

        # Step 2: Build coordination prompt with memory
        memory_context = self.get_memory_context(limit=5)
        prompt = f"""You are the Meta-Agent coordinating a multi-agent trading system.

REASONING PROTOCOL:
Think step-by-step before reaching your coordination decision:
1. Assess the current market regime and its implications
2. Determine which agents are most relevant for this regime
3. Consider how to weight conflicting agent recommendations
4. Anticipate potential failure modes in the coordination
5. Critique your own strategy - are you over/under-weighting any agent?

MARKET REGIME: {regime}

CURRENT DATA:
- Market: {data.get("symbol", "N/A")}
- Price: ${data.get("price", 0):.2f}
- Volatility: {data.get("volatility", 0):.2%}
- Volume Ratio: {data.get("volume_ratio", 1.0):.2f}x

{memory_context}

AVAILABLE SPECIALIST AGENTS:
- ResearchAgent: Analyzes fundamentals, news, sentiment
- SignalAgent: Technical analysis + momentum
- RiskAgent: Portfolio risk and position sizing
- ExecutionAgent: Order timing and execution

TASK: Based on the {regime} market regime, which agents should I activate and how should I weight their recommendations?

Provide your reasoning and agent activation strategy."""

        # Step 3: Use LLM reasoning to coordinate
        response = self.reason_with_llm(prompt)

        # Step 4: Execute coordinated analysis
        decision = {
            "meta_agent_reasoning": response["reasoning"],
            "market_regime": regime,
            "agent_activations": self._parse_activations(response["reasoning"]),
            "coordinated_decision": None,
        }

        # Step 5: Collect agent recommendations
        recommendations = {}
        for agent_name, weight in decision["agent_activations"].items():
            if agent_name in self.agents and weight > 0:
                agent = self.agents[agent_name]
                rec = agent.analyze(data)
                recommendations[agent_name] = {"recommendation": rec, "weight": weight}

        # Step 6: Synthesize final decision
        final_decision = self._synthesize_decision(recommendations)
        decision["coordinated_decision"] = final_decision

        # Log decision
        self.log_decision(decision)

        return decision

    def _detect_market_regime(self, data: dict[str, Any]) -> str:
        """
        Detect current market regime using volatility and trend indicators.

        Returns:
            Market regime string
        """
        volatility = data.get("volatility", 0.0)
        trend_strength = data.get("trend_strength", 0.0)

        # Simple regime classification (can be enhanced with ML)
        if volatility < 0.15:
            return "LOW_VOL"
        elif volatility > 0.30:
            return "HIGH_VOL"
        elif trend_strength > 0.6:
            return "TRENDING"
        else:
            return "RANGING"

    def _parse_activations(self, reasoning: str) -> dict[str, float]:
        """
        Parse agent activations from LLM reasoning.

        For now, use simple heuristics. Can be enhanced with structured output.

        Returns:
            Dict mapping agent names to activation weights
        """
        activations = {}

        # Default activations based on market regime
        if self.market_regime == "LOW_VOL":
            activations = {
                "ResearchAgent": 0.4,
                "SignalAgent": 0.3,
                "RiskAgent": 0.2,
                "ExecutionAgent": 0.1,
            }
        elif self.market_regime == "HIGH_VOL":
            activations = {
                "ResearchAgent": 0.2,
                "SignalAgent": 0.2,
                "RiskAgent": 0.5,  # High risk focus in volatile markets
                "ExecutionAgent": 0.1,
            }
        elif self.market_regime == "TRENDING":
            activations = {
                "ResearchAgent": 0.2,
                "SignalAgent": 0.5,  # High signal focus in trends
                "RiskAgent": 0.2,
                "ExecutionAgent": 0.1,
            }
        else:  # RANGING
            activations = {
                "ResearchAgent": 0.3,
                "SignalAgent": 0.3,
                "RiskAgent": 0.3,
                "ExecutionAgent": 0.1,
            }

        return activations

    def _synthesize_decision(self, recommendations: dict[str, dict]) -> dict[str, Any]:
        """
        Synthesize final decision from weighted agent recommendations.

        Args:
            recommendations: Dict of agent recommendations with weights

        Returns:
            Final trading decision
        """
        # Weighted vote
        total_buy_weight = 0.0
        total_sell_weight = 0.0
        total_hold_weight = 0.0

        for _agent_name, rec_data in recommendations.items():
            rec = rec_data["recommendation"]
            weight = rec_data["weight"]
            action = rec.get("action", "HOLD")

            if action == "BUY":
                total_buy_weight += weight
            elif action == "SELL":
                total_sell_weight += weight
            else:
                total_hold_weight += weight

        # Decide based on weighted votes
        max_weight = max(total_buy_weight, total_sell_weight, total_hold_weight)

        if max_weight == total_buy_weight and total_buy_weight > 0.5:
            action = "BUY"
            confidence = total_buy_weight
        elif max_weight == total_sell_weight and total_sell_weight > 0.5:
            action = "SELL"
            confidence = total_sell_weight
        else:
            action = "HOLD"
            confidence = total_hold_weight

        return {
            "action": action,
            "confidence": confidence,
            "buy_weight": total_buy_weight,
            "sell_weight": total_sell_weight,
            "hold_weight": total_hold_weight,
            "agent_recommendations": recommendations,
        }
