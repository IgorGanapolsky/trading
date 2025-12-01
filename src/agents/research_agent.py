"""
Research Agent: Multi-modal financial analysis

Responsibilities:
- Analyze company fundamentals
- Process news and sentiment (via RAG database)
- Evaluate market context
- Provide investment thesis

Inspired by P1GPT multi-modal analysis framework
"""

import logging
from typing import Dict, Any
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

# Import RAG retriever for semantic news search
try:
    from src.rag.vector_db.retriever import get_retriever

    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    logger.warning("RAG system not available - using fallback news")


class ResearchAgent(BaseAgent):
    """
    Research Agent analyzes fundamentals, news, and sentiment.

    Multi-modal approach:
    - Fundamental data (P/E, growth, margins)
    - News sentiment
    - Market context
    """

    def __init__(self):
        super().__init__(
            name="ResearchAgent", role="Multi-modal fundamental analysis and sentiment"
        )

        # Initialize RAG retriever if available
        if RAG_AVAILABLE:
            try:
                self.retriever = get_retriever()
                logger.info("RAG retriever initialized for ResearchAgent")
            except Exception as e:
                logger.warning(f"Failed to initialize RAG retriever: {e}")
                self.retriever = None
        else:
            self.retriever = None

    def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze fundamentals, news, and sentiment.

        Args:
            data: Contains symbol, fundamentals, news, market context

        Returns:
            Research analysis with investment thesis
        """
        symbol = data.get("symbol", "UNKNOWN")
        fundamentals = data.get("fundamentals", {})
        market_context = data.get("market_context", {})

        # Get news from RAG database or fallback to passed-in news
        if self.retriever:
            try:
                # Query RAG for recent news (last 7 days)
                logger.info(f"Querying RAG database for {symbol} news...")
                rag_articles = self.retriever.query_rag(
                    query=f"Latest news and analysis for {symbol}",
                    n_results=10,
                    ticker=symbol,
                    days_back=7,
                )

                # Convert RAG articles to expected news format
                news = []
                for article in rag_articles:
                    news.append(
                        {
                            "title": article["metadata"].get(
                                "title", article["content"][:100]
                            ),
                            "date": article["metadata"].get("date", "N/A"),
                            "sentiment": article["metadata"].get("sentiment", 0.5),
                            "source": article["metadata"].get("source", "unknown"),
                            "relevance": article["relevance_score"],
                        }
                    )

                logger.info(f"Retrieved {len(news)} articles from RAG for {symbol}")

            except Exception as e:
                logger.warning(f"Failed to query RAG, using fallback news: {e}")
                news = data.get("news", [])
        else:
            # Fallback to passed-in news if RAG not available
            news = data.get("news", [])

        # Build comprehensive research prompt
        memory_context = self.get_memory_context(limit=3)

        # Goldilocks Prompt: Principle-based with examples
        prompt = f"""Analyze {symbol} fundamentals and sentiment. Focus on value and risk.

FUNDAMENTALS:
P/E: {fundamentals.get('pe_ratio', 'N/A')} | Growth: {fundamentals.get('growth_rate', 'N/A')} | Margin: {fundamentals.get('profit_margin', 'N/A')} | Cap: {fundamentals.get('market_cap', 'N/A')}

NEWS:
{self._format_news(news)}

CONTEXT: {market_context.get('sector', 'N/A')} sector | Market: {market_context.get('market_trend', 'N/A')} | Vol: {market_context.get('volatility', 'N/A')}

{memory_context}

PRINCIPLES (Graham-Buffett):
- P/E < 15 is attractive, > 25 is expensive (weight: 30%)
- Consistent growth > 10% annually preferred (weight: 25%)
- Profit margin > 15% indicates pricing power (weight: 20%)
- News sentiment affects short-term, fundamentals drive long-term (weight: 25%)

EXAMPLES:
Example 1 - Strong Fundamental Buy:
STRENGTH: 8
SENTIMENT: 0.6
THESIS: Low P/E of 12 with 18% growth suggests undervalued quality. Recent positive earnings beat confirms trajectory.
RECOMMENDATION: BUY
CONFIDENCE: 0.78
RISKS: Sector rotation risk, margin compression if input costs rise

Example 2 - Avoid Despite Hype:
STRENGTH: 3
SENTIMENT: 0.8
THESIS: High sentiment but P/E of 45 prices in perfection. Any miss will punish stock. Wait for pullback.
RECOMMENDATION: HOLD
CONFIDENCE: 0.65
RISKS: Valuation compression, growth deceleration, sentiment reversal

NOW ANALYZE {symbol}:
STRENGTH: [1-10]
SENTIMENT: [-1 to +1]
THESIS: [2-3 sentences on value proposition]
RECOMMENDATION: [BUY/SELL/HOLD]
CONFIDENCE: [0-1]
RISKS: [top 2 risks]"""

        # Get LLM analysis
        response = self.reason_with_llm(prompt)

        # Parse response
        analysis = self._parse_research_response(response["reasoning"])
        analysis["full_reasoning"] = response["reasoning"]

        # Log decision
        self.log_decision(analysis)

        return analysis

    def _format_news(self, news: list) -> str:
        """Format news items for prompt."""
        if not news:
            return "No recent news available."

        formatted = ""
        for i, item in enumerate(news[:5], 1):  # Top 5 news items
            formatted += (
                f"{i}. {item.get('title', 'N/A')} ({item.get('date', 'N/A')})\n"
            )
            formatted += f"   Sentiment: {item.get('sentiment', 'neutral')}\n"

        return formatted

    def _parse_research_response(self, reasoning: str) -> Dict[str, Any]:
        """
        Parse LLM response into structured analysis.

        Args:
            reasoning: LLM response text

        Returns:
            Structured analysis dict
        """
        lines = reasoning.split("\n")
        analysis = {
            "strength": 5,  # Default values
            "sentiment": 0.0,
            "thesis": "",
            "action": "HOLD",
            "confidence": 0.5,
            "risks": "",
        }

        for line in lines:
            line = line.strip()
            if line.startswith("STRENGTH:"):
                try:
                    analysis["strength"] = int(line.split(":")[1].strip())
                except:
                    pass
            elif line.startswith("SENTIMENT:"):
                try:
                    analysis["sentiment"] = float(line.split(":")[1].strip())
                except:
                    pass
            elif line.startswith("THESIS:"):
                analysis["thesis"] = line.split(":", 1)[1].strip()
            elif line.startswith("RECOMMENDATION:"):
                rec = line.split(":")[1].strip().upper()
                if rec in ["BUY", "SELL", "HOLD"]:
                    analysis["action"] = rec
            elif line.startswith("CONFIDENCE:"):
                try:
                    analysis["confidence"] = float(line.split(":")[1].strip())
                except:
                    pass
            elif line.startswith("RISKS:"):
                analysis["risks"] = line.split(":", 1)[1].strip()

        return analysis
