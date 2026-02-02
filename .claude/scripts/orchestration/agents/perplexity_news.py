#!/usr/bin/env python3
"""
Perplexity-Powered News Agent for Trading System

Uses Perplexity Pro API for real-time market intelligence:
- Breaking news affecting SPY/options
- Fed speaker schedules and economic events
- Earnings announcements
- Analyst upgrades/downgrades
- Unusual options activity

Integrates with swarm orchestration for pre-trade validation.
"""

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx


@dataclass
class MarketEvent:
    """A market-moving event detected by Perplexity."""

    event_type: str  # 'earnings', 'fed', 'economic', 'news', 'options_flow'
    headline: str
    impact_level: str  # 'high', 'medium', 'low'
    ticker: str | None
    timestamp: datetime
    source: str
    details: str


class PerplexityNewsAgent:
    """
    Real-time market news agent powered by Perplexity Pro.

    Provides autonomous market scanning for iron condor trading:
    - Pre-trade: Check for events that could blow through strikes
    - Intraday: Monitor for breaking news requiring position adjustment
    - EOD: Summarize day's events for learning
    """

    def __init__(self):
        self.api_key = os.environ.get("PERPLEXITY_API_KEY", "")
        self.base_url = "https://api.perplexity.ai/chat/completions"
        self.model = "sonar"  # Perplexity's search-grounded model

    async def search(self, query: str, recency: str = "day") -> dict[str, Any]:
        """
        Execute a Perplexity search with recency filtering.

        Args:
            query: Natural language search query
            recency: Time filter - 'day', 'week', 'month', 'year'

        Returns:
            Search results with sources
        """
        if not self.api_key:
            return {"error": "PERPLEXITY_API_KEY not configured", "results": []}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a financial market analyst. Provide concise, factual answers about market events. Focus on events that could affect SPY options prices.",
                },
                {"role": "user", "content": query},
            ],
            "search_recency_filter": recency,
            "return_citations": True,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers=headers,
                    json=payload,
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()

                return {
                    "answer": data["choices"][0]["message"]["content"],
                    "citations": data.get("citations", []),
                    "model": data.get("model", self.model),
                }
        except httpx.HTTPError as e:
            return {"error": str(e), "results": []}

    async def get_pre_trade_intel(self) -> dict[str, Any]:
        """
        Get market intelligence BEFORE opening an iron condor.

        Checks:
        1. Fed speakers today
        2. Economic data releases
        3. Major earnings that could move SPY
        4. Unusual options activity
        """
        queries = [
            ("fed_speakers", "Are there any Federal Reserve speakers or FOMC events today?"),
            ("economic_data", "What economic data releases are scheduled today? GDP, jobs, CPI, etc."),
            ("spy_earnings", "Are there any S&P 500 companies reporting earnings today that could move SPY?"),
            ("options_flow", "Is there any unusual options activity on SPY today?"),
        ]

        results = {}
        risk_score = 0.0

        for key, query in queries:
            result = await self.search(query, recency="day")
            results[key] = result

            # Assess risk from answer
            if result.get("answer"):
                answer_lower = result["answer"].lower()
                if any(word in answer_lower for word in ["fed", "fomc", "powell", "rate"]):
                    risk_score += 0.3
                if any(word in answer_lower for word in ["cpi", "jobs", "gdp", "inflation"]):
                    risk_score += 0.2
                if any(word in answer_lower for word in ["earnings", "guidance", "beat", "miss"]):
                    risk_score += 0.15

        # Determine trade recommendation
        if risk_score >= 0.5:
            recommendation = "AVOID"
            reason = "High-impact events today could cause volatility beyond iron condor strikes"
        elif risk_score >= 0.3:
            recommendation = "CAUTION"
            reason = "Moderate event risk - consider wider strikes or smaller position"
        else:
            recommendation = "CLEAR"
            reason = "No major market-moving events detected"

        return {
            "risk_score": round(min(risk_score, 1.0), 2),
            "recommendation": recommendation,
            "reason": reason,
            "intel": results,
            "timestamp": datetime.now().isoformat(),
        }

    async def get_breaking_news(self, ticker: str = "SPY") -> dict[str, Any]:
        """Get breaking news that could affect a position."""
        query = f"Breaking news affecting {ticker} stock price in the last hour"
        result = await self.search(query, recency="day")

        events = []
        if result.get("answer"):
            # Parse for high-impact keywords
            answer = result["answer"]
            impact = "low"

            if any(word in answer.lower() for word in ["crash", "surge", "halt", "breaking"]):
                impact = "high"
            elif any(word in answer.lower() for word in ["rise", "fall", "move", "change"]):
                impact = "medium"

            events.append(
                MarketEvent(
                    event_type="news",
                    headline=answer[:200],
                    impact_level=impact,
                    ticker=ticker,
                    timestamp=datetime.now(),
                    source="perplexity",
                    details=answer,
                )
            )

        return {
            "ticker": ticker,
            "events": [e.__dict__ for e in events],
            "has_breaking_news": len(events) > 0 and events[0].impact_level != "low",
        }

    async def get_phil_town_research(self, topic: str) -> dict[str, Any]:
        """
        Research Phil Town investing concepts for weekend learning.

        Topics: 'rule_1', 'big_5', 'moat', 'management', 'margin_of_safety'
        """
        topic_queries = {
            "rule_1": "Phil Town Rule #1 investing - what are the key principles for never losing money?",
            "big_5": "Phil Town Big 5 numbers for stock analysis - ROIC, sales growth, EPS growth, equity growth, cash flow growth",
            "moat": "What makes a company have a strong economic moat according to Phil Town?",
            "management": "How to evaluate company management quality using Phil Town's methods",
            "margin_of_safety": "Phil Town margin of safety calculation for stock valuation",
        }

        query = topic_queries.get(topic, f"Phil Town investing advice on {topic}")
        result = await self.search(query, recency="year")

        return {
            "topic": topic,
            "research": result.get("answer", ""),
            "sources": result.get("citations", []),
        }


# Integration with swarm orchestration
async def perplexity_news_signal() -> dict[str, Any]:
    """
    Generate trading signal from Perplexity news analysis.

    Returns signal in swarm-compatible format for aggregation.
    """
    agent = PerplexityNewsAgent()

    # Get pre-trade intelligence
    intel = await agent.get_pre_trade_intel()

    # Convert to swarm signal format
    # Higher signal = safer to trade, Lower = more risky
    signal = 1.0 - intel["risk_score"]

    return {
        "signal": round(signal, 2),
        "confidence": 0.85,  # Perplexity is generally reliable
        "data": {
            "risk_score": intel["risk_score"],
            "recommendation": intel["recommendation"],
            "reason": intel["reason"],
            "intel_summary": {
                k: v.get("answer", "")[:100] for k, v in intel.get("intel", {}).items()
            },
        },
    }


async def main():
    """Demo the Perplexity news agent."""
    agent = PerplexityNewsAgent()

    if not agent.api_key:
        print("⚠️  PERPLEXITY_API_KEY not set - using mock mode")
        print("\nTo enable real searches, add to .env:")
        print("  PERPLEXITY_API_KEY=pplx-xxxx...")
        return

    print("=== Pre-Trade Intelligence ===")
    intel = await agent.get_pre_trade_intel()
    print(f"Risk Score: {intel['risk_score']}")
    print(f"Recommendation: {intel['recommendation']}")
    print(f"Reason: {intel['reason']}")

    print("\n=== Breaking News Check ===")
    news = await agent.get_breaking_news("SPY")
    print(f"Has breaking news: {news['has_breaking_news']}")

    print("\n=== Swarm Signal ===")
    signal = await perplexity_news_signal()
    print(f"Signal: {signal['signal']} (higher = safer)")
    print(f"Confidence: {signal['confidence']}")


if __name__ == "__main__":
    asyncio.run(main())
