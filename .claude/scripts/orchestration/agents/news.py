"""
News Analysis Agent

Monitors breaking news and events that could impact trading:
- Major market-moving news
- Earnings announcements
- Macro economic events
- Fed announcements
"""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from .base import BaseAgent

ET = ZoneInfo("America/New_York")


class NewsAgent(BaseAgent):
    """News and events monitoring agent."""

    # High-impact events that warrant caution
    HIGH_IMPACT_KEYWORDS = [
        "fed",
        "fomc",
        "rate decision",
        "inflation",
        "cpi",
        "jobs report",
        "nfp",
        "gdp",
        "earnings",
        "war",
        "crisis",
        "crash",
        "halt",
        "emergency",
    ]

    def __init__(self):
        super().__init__("news")

    async def analyze(self) -> dict[str, Any]:
        """Analyze news and upcoming events."""
        # In production, this would fetch from news APIs
        # (Alpha Vantage, Benzinga, etc.)

        # Mock data for typical day
        breaking_news: list[dict] = []
        earnings_today: list[str] = []  # SPY components with earnings
        macro_events: list[dict] = []

        # Check if it's a high-risk day
        today = datetime.now(ET)
        day_of_week = today.weekday()

        # FOMC days are typically Wednesdays
        is_fomc_week = False  # Would check calendar

        # Jobs report is first Friday
        is_jobs_friday = day_of_week == 4 and today.day <= 7

        # Calculate risk level
        risk_factors = []

        if breaking_news:
            for news in breaking_news:
                headline = news.get("headline", "").lower()
                if any(kw in headline for kw in self.HIGH_IMPACT_KEYWORDS):
                    risk_factors.append(f"high_impact_news: {headline[:50]}")

        if earnings_today:
            risk_factors.append(f"earnings: {len(earnings_today)} SPY components")

        if is_fomc_week:
            risk_factors.append("fomc_week")

        if is_jobs_friday:
            risk_factors.append("jobs_report_day")

        # Calculate signal
        # Default is neutral (0.5) - no news is good news for iron condors
        if len(risk_factors) == 0:
            signal = 0.6  # Quiet day is good
            risk_level = "low"
        elif len(risk_factors) == 1:
            signal = 0.5  # Proceed with caution
            risk_level = "moderate"
        elif len(risk_factors) == 2:
            signal = 0.35  # Consider waiting
            risk_level = "elevated"
        else:
            signal = 0.2  # High risk, avoid new positions
            risk_level = "high"

        # Confidence is lower for news (subjective)
        confidence = 0.6

        return {
            "signal": round(signal, 3),
            "confidence": round(confidence, 3),
            "data": {
                "breaking_news": breaking_news,
                "earnings_today": earnings_today,
                "macro_events": macro_events,
                "risk_factors": risk_factors,
                "risk_level": risk_level,
                "is_fomc_week": is_fomc_week,
                "is_jobs_friday": is_jobs_friday,
                "recommendation": self._get_recommendation(risk_level),
                "market_open": self._is_market_open(),
            },
        }

    def _is_market_open(self) -> bool:
        """Check if market is currently open."""
        now = datetime.now(ET)
        if now.weekday() >= 5:  # Weekend
            return False

        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)

        return market_open <= now <= market_close

    def _get_recommendation(self, risk_level: str) -> str:
        """Generate news-based recommendation."""
        recommendations = {
            "low": "clear_to_trade",
            "moderate": "proceed_with_smaller_size",
            "elevated": "consider_waiting",
            "high": "avoid_new_positions",
        }
        return recommendations.get(risk_level, "review_manually")
