import logging
from datetime import datetime
from typing import Any, Optional

import requests
from bs4 import BeautifulSoup
from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class BogleHeadsAgent(BaseAgent):
    """
    BogleHeads Agent: "The Voice of Reason"

    Responsibilities:
    - Monitor BogleHeads forum for market sentiment.
    - Provide "Stay the Course" sanity checks.
    - Veto high-risk/speculative trades that violate Boglehead philosophy.

    Philosophy:
    - Low cost, broad diversification (VTI/VXUS/BND).
    - Buy and hold.
    - Ignore noise.
    """

    def __init__(self):
        super().__init__(
            name="BogleHeadsAgent",
            role="Long-term investment philosophy and market sentiment sanity check",
            model="claude-3-opus-20240229",
        )
        self.base_url = "https://www.bogleheads.org/forum/viewforum.php?f=10"  # Investing - Theory, News & General

    def analyze(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Analyze market sentiment via BogleHeads forum.

        Args:
            data: Contains 'symbol' (optional)

        Returns:
            Sentiment analysis and strategic advice.
        """
        symbol = data.get("symbol")

        logger.info("👴 BogleHeads Agent consulting the wisdom of the elders...")

        # 1. Scrape Forum Topics
        topics = self._scrape_forum_topics()

        if not topics:
            return {
                "agent": self.name,
                "signal": "NEUTRAL",
                "confidence": 0.0,
                "reasoning": "Failed to fetch forum data. Defaulting to 'Stay the Course'.",
            }

        # 2. Analyze Sentiment with LLM
        prompt = self._build_sentiment_prompt(topics, symbol)
        llm_response = self.reason_with_llm(prompt)

        result = {
            "agent": self.name,
            "symbol": symbol,
            "signal": llm_response.get("decision", "HOLD"),  # HOLD usually means "Stay the Course"
            "confidence": llm_response.get("confidence", 0.5),
            "reasoning": llm_response.get("reasoning", "Stay the course."),
            "bogleheads_sentiment": llm_response.get("sentiment_summary", "Unknown"),
            "timestamp": datetime.now().isoformat(),
        }

        self.log_decision(result)
        return result

    def _scrape_forum_topics(self) -> list[str]:
        """Scrape the first page of topic titles."""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
            }
            response = requests.get(self.base_url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")

            # Bogleheads uses phpBB. Topics are usually in <a class="topictitle">
            topic_links = soup.find_all("a", class_="topictitle")

            titles = [link.text.strip() for link in topic_links]
            return titles[:20]  # Return top 20 topics

        except Exception as e:
            logger.error(f"Failed to scrape BogleHeads: {e}")
            return []

    def _build_sentiment_prompt(self, topics: list[str], symbol: Optional[str]) -> str:
        topics_str = "\n".join([f"- {t}" for t in topics])

        return f"""You are the BogleHeads Agent, representing the wisdom of the BogleHeads community (John Bogle's followers).

        PHILOSOPHY:
        - Low-cost index funds (VTI, VOO, VXUS, BND).
        - Buy and hold forever.
        - "Stay the course" - ignore market noise.
        - Market timing is impossible.
        - Speculation is gambling.

        CURRENT FORUM TOPICS (Investing - Theory, News & General):
        {topics_str}

        TASK:
        1. Analyze the "Mood" of the forum based on these topic titles. Are people panicking? Euphoric? Discussing tax loss harvesting?
        2. If the user is asking about '{symbol}', provide specific advice based on Boglehead principles.
           - If '{symbol}' is a broad index ETF (SPY, VOO, VTI, QQQ), you generally APPROVE.
           - If '{symbol}' is a single stock or crypto, you generally DISAPPROVE or advise CAUTION (max 5% of portfolio).
           - If '{symbol}' is a leveraged ETF (TQQQ, SOXL), you strongly DISAPPROVE.

        OUTPUT FORMAT (JSON):
        {{
            "sentiment_summary": "Brief summary of forum mood",
            "decision": "BUY" (for index funds) / "HOLD" (stay the course) / "SELL" (if speculative garbage),
            "confidence": 0.0 to 1.0,
            "reasoning": "Explanation in the voice of a wise, experienced Boglehead investor."
        }}
        """
