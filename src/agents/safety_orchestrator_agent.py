"""
Safety Orchestrator Agent: Coordinates All Safety Agents

Responsibilities:
- Orchestrate safety analysis, quality monitoring, and value discovery
- Coordinate multiple safety agents in parallel
- Aggregate safety recommendations
- Provide unified safety decision

Ensures comprehensive safety analysis across all agents.
"""

import logging
from datetime import datetime
from typing import Any

from .base_agent import BaseAgent
from .quality_monitor_agent import QualityMonitorAgent
from .safety_analysis_agent import SafetyAnalysisAgent
from .value_discovery_agent import ValueDiscoveryAgent

logger = logging.getLogger(__name__)


class SafetyOrchestratorAgent(BaseAgent):
    """
    Safety Orchestrator Agent coordinates all safety-related agents.

    Key functions:
    - Orchestrate safety analysis for trades
    - Coordinate quality monitoring
    - Manage value discovery
    - Aggregate recommendations
    """

    def __init__(self):
        super().__init__(
            name="SafetyOrchestratorAgent",
            role="Orchestrate all safety agents for comprehensive analysis",
        )

        # Initialize sub-agents
        self.safety_analysis_agent = SafetyAnalysisAgent()
        self.quality_monitor_agent = QualityMonitorAgent()
        self.value_discovery_agent = ValueDiscoveryAgent()

        logger.info("Safety Orchestrator Agent initialized with 3 sub-agents")

    def analyze(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Orchestrate comprehensive safety analysis.

        Args:
            data: Contains analysis_type and relevant data:
                - "trade_analysis": {symbol, market_price}
                - "quality_monitoring": {positions, portfolio_value}
                - "value_discovery": {watchlist, market_prices}
                - "comprehensive": {all of the above}

        Returns:
            Comprehensive safety analysis with recommendations
        """
        analysis_type = data.get("analysis_type", "trade_analysis")

        if analysis_type == "trade_analysis":
            return self._analyze_trade(data)
        elif analysis_type == "quality_monitoring":
            return self._monitor_quality(data)
        elif analysis_type == "value_discovery":
            return self._discover_value(data)
        elif analysis_type == "comprehensive":
            return self._comprehensive_analysis(data)
        else:
            return {
                "action": "ERROR",
                "message": f"Unknown analysis type: {analysis_type}",
            }

    def _analyze_trade(self, data: dict[str, Any]) -> dict[str, Any]:
        """Analyze a specific trade opportunity."""
        symbol = data.get("symbol", "")
        market_price = data.get("market_price", 0.0)

        if not symbol or market_price <= 0:
            return {
                "action": "REJECT",
                "reason": "Invalid symbol or price",
            }

        # Get safety analysis
        safety_data = {
            "symbol": symbol,
            "market_price": market_price,
            "force_refresh": data.get("force_refresh", False),
        }

        safety_analysis = self.safety_analysis_agent.analyze(safety_data)

        # Build comprehensive response
        response = {
            "analysis_type": "trade_analysis",
            "symbol": symbol,
            "market_price": market_price,
            "safety_analysis": safety_analysis,
            "overall_recommendation": safety_analysis.get("action", "REJECT"),
            "confidence": safety_analysis.get("confidence", 0.0),
            "timestamp": datetime.now().isoformat(),
        }

        # Log decision
        self.log_decision(response)

        return response

    def _monitor_quality(self, data: dict[str, Any]) -> dict[str, Any]:
        """Monitor portfolio quality."""
        positions = data.get("positions", [])
        portfolio_value = data.get("portfolio_value", 0.0)

        # Get quality monitoring
        quality_data = {
            "positions": positions,
            "portfolio_value": portfolio_value,
        }

        quality_report = self.quality_monitor_agent.analyze(quality_data)

        # Build comprehensive response
        response = {
            "analysis_type": "quality_monitoring",
            "quality_report": quality_report,
            "timestamp": datetime.now().isoformat(),
        }

        # Log decision
        self.log_decision(response)

        return response

    def _discover_value(self, data: dict[str, Any]) -> dict[str, Any]:
        """Discover undervalued opportunities."""
        watchlist = data.get("watchlist", [])
        market_prices = data.get("market_prices", {})

        # Get value discovery
        discovery_data = {
            "watchlist": watchlist,
            "market_prices": market_prices,
        }

        opportunities = self.value_discovery_agent.analyze(discovery_data)

        # Build comprehensive response
        response = {
            "analysis_type": "value_discovery",
            "opportunities": opportunities,
            "timestamp": datetime.now().isoformat(),
        }

        # Log decision
        self.log_decision(response)

        return response

    def _comprehensive_analysis(self, data: dict[str, Any]) -> dict[str, Any]:
        """Perform comprehensive safety analysis."""

        # Run all analyses in parallel (simulated - in production would use async)
        results = {}

        # Trade analysis if provided
        if "symbol" in data and "market_price" in data:
            results["trade_analysis"] = self._analyze_trade(data)

        # Quality monitoring if provided
        if "positions" in data:
            results["quality_monitoring"] = self._monitor_quality(data)

        # Value discovery if provided
        if "watchlist" in data:
            results["value_discovery"] = self._discover_value(data)

        # Get LLM synthesis
        memory_context = self.get_memory_context(limit=5)

        prompt = self._build_comprehensive_prompt(results, memory_context)

        llm_response = self.reason_with_llm(prompt)

        # Combine all results
        comprehensive = {
            "analysis_type": "comprehensive",
            "results": results,
            "synthesis": self._parse_synthesis(llm_response.get("reasoning", "")),
            "full_reasoning": llm_response.get("reasoning", ""),
            "timestamp": datetime.now().isoformat(),
        }

        # Log decision
        self.log_decision(comprehensive)

        return comprehensive

    def _build_comprehensive_prompt(self, results: dict[str, Any], memory_context: str) -> str:
        """Build LLM prompt for comprehensive analysis synthesis."""

        results_summary = ""
        for analysis_type, result in results.items():
            results_summary += f"\n{analysis_type.upper()}:\n{str(result)}\n"

        prompt = f"""You are a Safety Orchestrator Agent synthesizing comprehensive safety analysis.

ANALYSIS RESULTS:
{results_summary}

{memory_context}

TASK: Provide comprehensive safety synthesis:
1. Overall Safety Assessment (SAFE / CAUTIOUS / RISKY)
2. Key Findings (most important safety insights)
3. Priority Actions (what to do next)
4. Risk Level (LOW / MEDIUM / HIGH)
5. Investment Readiness (READY / WAIT / AVOID)

Format your response as:
SAFETY_ASSESSMENT: [SAFE/CAUTIOUS/RISKY]
KEY_FINDINGS: [key findings]
PRIORITY_ACTIONS: [priority actions]
RISK_LEVEL: [LOW/MEDIUM/HIGH]
INVESTMENT_READINESS: [READY/WAIT/AVOID]"""

        return prompt

    def _parse_synthesis(self, reasoning: str) -> dict[str, Any]:
        """Parse LLM synthesis response."""
        lines = reasoning.split("\n")
        synthesis = {
            "safety_assessment": "CAUTIOUS",
            "key_findings": "",
            "priority_actions": "",
            "risk_level": "MEDIUM",
            "investment_readiness": "WAIT",
        }

        for line in lines:
            line = line.strip()
            if line.startswith("SAFETY_ASSESSMENT:"):
                assessment = line.split(":")[1].strip().upper()
                if assessment in ["SAFE", "CAUTIOUS", "RISKY"]:
                    synthesis["safety_assessment"] = assessment
            elif line.startswith("KEY_FINDINGS:"):
                synthesis["key_findings"] = line.split(":", 1)[1].strip()
            elif line.startswith("PRIORITY_ACTIONS:"):
                synthesis["priority_actions"] = line.split(":", 1)[1].strip()
            elif line.startswith("RISK_LEVEL:"):
                risk = line.split(":")[1].strip().upper()
                if risk in ["LOW", "MEDIUM", "HIGH"]:
                    synthesis["risk_level"] = risk
            elif line.startswith("INVESTMENT_READINESS:"):
                readiness = line.split(":")[1].strip().upper()
                if readiness in ["READY", "WAIT", "AVOID"]:
                    synthesis["investment_readiness"] = readiness

        return synthesis
