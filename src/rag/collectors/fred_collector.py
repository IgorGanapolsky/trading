"""
FRED (Federal Reserve Economic Data) Collector

Collects macroeconomic data from the Federal Reserve Bank of St. Louis FRED API.
Essential for understanding macro regime shifts that affect all trading decisions.

Key Data Series:
- Interest Rates: FEDFUNDS (Fed Funds), DGS10 (10-Year Treasury)
- Inflation: CPIAUCSL (CPI), PCEPI (PCE)
- Employment: UNRATE (Unemployment), PAYEMS (Non-farm Payrolls)
- GDP/Growth: GDP, GDPC1 (Real GDP)
- Market Stress: VIXCLS (VIX), BAMLH0A0HYM2 (High Yield Spread)
- Consumer: UMCSENT (Consumer Sentiment), RSAFS (Retail Sales)

API: https://fred.stlouisfed.org/docs/api/fred/
Free tier: 500 requests/day (sufficient for daily updates)

Author: Trading System
Created: 2025-12-01
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Optional

import requests
from src.rag.collectors.base_collector import BaseNewsCollector

logger = logging.getLogger(__name__)


# Key economic indicators to track
FRED_SERIES = {
    # Interest Rates
    "FEDFUNDS": {
        "name": "Federal Funds Rate",
        "category": "interest_rates",
        "frequency": "monthly",
        "impact": "high",
    },
    "DGS10": {
        "name": "10-Year Treasury Yield",
        "category": "interest_rates",
        "frequency": "daily",
        "impact": "high",
    },
    "DGS2": {
        "name": "2-Year Treasury Yield",
        "category": "interest_rates",
        "frequency": "daily",
        "impact": "high",
    },
    "T10Y2Y": {
        "name": "10-2 Year Treasury Spread",
        "category": "interest_rates",
        "frequency": "daily",
        "impact": "high",
        "description": "Yield curve inversion indicator",
    },
    # Inflation
    "CPIAUCSL": {
        "name": "Consumer Price Index",
        "category": "inflation",
        "frequency": "monthly",
        "impact": "high",
    },
    "PCEPI": {
        "name": "PCE Price Index",
        "category": "inflation",
        "frequency": "monthly",
        "impact": "high",
        "description": "Fed's preferred inflation measure",
    },
    "MICH": {
        "name": "Inflation Expectations",
        "category": "inflation",
        "frequency": "monthly",
        "impact": "medium",
    },
    # Employment
    "UNRATE": {
        "name": "Unemployment Rate",
        "category": "employment",
        "frequency": "monthly",
        "impact": "high",
    },
    "PAYEMS": {
        "name": "Non-farm Payrolls",
        "category": "employment",
        "frequency": "monthly",
        "impact": "high",
    },
    "ICSA": {
        "name": "Initial Jobless Claims",
        "category": "employment",
        "frequency": "weekly",
        "impact": "medium",
    },
    # GDP & Growth
    "GDP": {
        "name": "Gross Domestic Product",
        "category": "growth",
        "frequency": "quarterly",
        "impact": "high",
    },
    "GDPC1": {
        "name": "Real GDP",
        "category": "growth",
        "frequency": "quarterly",
        "impact": "high",
    },
    # Market Stress
    "VIXCLS": {
        "name": "VIX Volatility Index",
        "category": "market_stress",
        "frequency": "daily",
        "impact": "high",
    },
    "BAMLH0A0HYM2": {
        "name": "High Yield Spread",
        "category": "market_stress",
        "frequency": "daily",
        "impact": "high",
        "description": "Credit stress indicator",
    },
    "TEDRATE": {
        "name": "TED Spread",
        "category": "market_stress",
        "frequency": "daily",
        "impact": "medium",
    },
    # Consumer
    "UMCSENT": {
        "name": "Consumer Sentiment",
        "category": "consumer",
        "frequency": "monthly",
        "impact": "medium",
    },
    "RSAFS": {
        "name": "Retail Sales",
        "category": "consumer",
        "frequency": "monthly",
        "impact": "medium",
    },
    # Housing
    "HOUST": {
        "name": "Housing Starts",
        "category": "housing",
        "frequency": "monthly",
        "impact": "medium",
    },
    "MORTGAGE30US": {
        "name": "30-Year Mortgage Rate",
        "category": "housing",
        "frequency": "weekly",
        "impact": "medium",
    },
    # Manufacturing
    "INDPRO": {
        "name": "Industrial Production",
        "category": "manufacturing",
        "frequency": "monthly",
        "impact": "medium",
    },
}


class FREDCollector(BaseNewsCollector):
    """
    Collector for Federal Reserve Economic Data (FRED).

    Fetches macroeconomic indicators and converts them to trading signals.
    """

    BASE_URL = "https://api.stlouisfed.org/fred"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize FRED collector.

        Args:
            api_key: FRED API key (get free at https://fred.stlouisfed.org/docs/api/api_key.html)
        """
        super().__init__(source_name="fred")
        self.api_key = api_key or os.getenv("FRED_API_KEY")

        if not self.api_key:
            logger.warning(
                "FRED_API_KEY not set. Get free key at "
                "https://fred.stlouisfed.org/docs/api/api_key.html"
            )

        self.series_config = FRED_SERIES

    def collect_ticker_news(self, ticker: str, days_back: int = 7) -> list[dict[str, Any]]:
        """
        Collect economic data relevant to a ticker.

        For macro indicators, ticker is ignored - we return all relevant data.

        Args:
            ticker: Stock ticker (ignored for macro data)
            days_back: Days of data to collect

        Returns:
            List of normalized economic data articles
        """
        return self.collect_market_news(days_back=days_back)

    def collect_market_news(self, days_back: int = 30) -> list[dict[str, Any]]:
        """
        Collect all key economic indicators.

        Args:
            days_back: Days of data to collect

        Returns:
            List of normalized articles with economic data
        """
        if not self.api_key:
            logger.warning("FRED API key not configured, skipping collection")
            return []

        articles = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        for series_id, config in self.series_config.items():
            try:
                data = self._fetch_series(
                    series_id,
                    start_date.strftime("%Y-%m-%d"),
                    end_date.strftime("%Y-%m-%d"),
                )

                if data:
                    article = self._convert_to_article(series_id, config, data)
                    if article:
                        articles.append(article)

            except Exception as e:
                logger.warning(f"Failed to fetch {series_id}: {e}")
                continue

        logger.info(f"Collected {len(articles)} FRED economic indicators")
        return articles

    def _fetch_series(
        self, series_id: str, start_date: str, end_date: str
    ) -> Optional[dict[str, Any]]:
        """
        Fetch a single FRED series.

        Args:
            series_id: FRED series ID
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Series data dict or None
        """
        url = f"{self.BASE_URL}/series/observations"
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "observation_start": start_date,
            "observation_end": end_date,
            "sort_order": "desc",
            "limit": 10,
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            observations = data.get("observations", [])

            if not observations:
                return None

            return {
                "series_id": series_id,
                "observations": observations,
                "latest_value": observations[0].get("value", ".") if observations else None,
                "latest_date": observations[0].get("date") if observations else None,
            }

        except requests.RequestException as e:
            logger.warning(f"FRED API request failed for {series_id}: {e}")
            return None

    def _convert_to_article(
        self, series_id: str, config: dict[str, Any], data: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """
        Convert FRED data to article format.

        Args:
            series_id: FRED series ID
            config: Series configuration
            data: Fetched data

        Returns:
            Normalized article dict
        """
        latest_value = data.get("latest_value")
        latest_date = data.get("latest_date")

        if not latest_value or latest_value == ".":
            return None

        try:
            value = float(latest_value)
        except (ValueError, TypeError):
            return None

        # Generate analysis based on indicator type
        analysis = self._generate_analysis(series_id, config, value, data)

        content = f"""Economic Indicator: {config["name"]} ({series_id})
Category: {config["category"]}
Latest Value: {value}
Date: {latest_date}
Impact Level: {config["impact"]}

{analysis}

Historical Context:
{self._format_history(data.get("observations", []))}
"""

        return self.normalize_article(
            title=f"{config['name']} Update: {value}",
            content=content,
            url=f"https://fred.stlouisfed.org/series/{series_id}",
            published_date=latest_date,
            ticker="MACRO",
            sentiment=self._calculate_sentiment(series_id, value, data),
        )

    def _generate_analysis(
        self,
        series_id: str,
        config: dict[str, Any],
        value: float,
        data: dict[str, Any],
    ) -> str:
        """Generate analysis text based on indicator."""
        observations = data.get("observations", [])

        # Calculate change if we have history
        if len(observations) >= 2:
            try:
                prev_value = float(observations[1].get("value", 0))
                if prev_value != 0:
                    change = ((value - prev_value) / abs(prev_value)) * 100
                    direction = "increased" if change > 0 else "decreased"
                    change_text = f"The {config['name']} has {direction} by {abs(change):.2f}% from the previous reading."
                else:
                    change_text = ""
            except (ValueError, TypeError):
                change_text = ""
        else:
            change_text = ""

        # Add indicator-specific analysis
        category_analysis = {
            "interest_rates": self._analyze_rates(series_id, value),
            "inflation": self._analyze_inflation(series_id, value),
            "employment": self._analyze_employment(series_id, value),
            "market_stress": self._analyze_stress(series_id, value),
            "growth": self._analyze_growth(series_id, value),
            "consumer": self._analyze_consumer(series_id, value),
        }

        specific = category_analysis.get(config["category"], "")

        return f"{change_text}\n\n{specific}".strip()

    def _analyze_rates(self, series_id: str, value: float) -> str:
        """Analyze interest rate indicators."""
        if series_id == "T10Y2Y":
            if value < 0:
                return "SIGNAL: Yield curve INVERTED - historically precedes recessions. Risk-off environment likely."
            elif value < 0.5:
                return "SIGNAL: Yield curve FLAT - late cycle indicator. Monitor for potential inversion."
            else:
                return "SIGNAL: Yield curve NORMAL - healthy economic expansion signal."
        elif series_id == "FEDFUNDS":
            if value > 5:
                return "SIGNAL: Restrictive monetary policy. Headwind for equities, especially growth stocks."
            elif value < 2:
                return "SIGNAL: Accommodative policy. Tailwind for risk assets."
            else:
                return "SIGNAL: Neutral monetary policy stance."
        return ""

    def _analyze_inflation(self, series_id: str, value: float) -> str:
        """Analyze inflation indicators."""
        if value > 4:
            return "SIGNAL: HIGH inflation - Fed likely hawkish. Favor value over growth, commodities over bonds."
        elif value > 2.5:
            return "SIGNAL: Above-target inflation - monitor for policy response."
        elif value < 1.5:
            return "SIGNAL: LOW inflation/disinflation - Fed may turn dovish. Favor growth stocks, bonds."
        return "SIGNAL: Inflation near Fed target (2%). Balanced environment."

    def _analyze_employment(self, series_id: str, value: float) -> str:
        """Analyze employment indicators."""
        if series_id == "UNRATE":
            if value < 4:
                return (
                    "SIGNAL: Very tight labor market - wage pressure likely. Late cycle indicator."
                )
            elif value > 6:
                return (
                    "SIGNAL: Elevated unemployment - recession signal. Risk-off, favor defensives."
                )
            else:
                return "SIGNAL: Healthy labor market - supports consumer spending."
        elif series_id == "ICSA":
            if value > 250000:
                return "SIGNAL: Rising jobless claims - economic weakness emerging."
            else:
                return "SIGNAL: Low claims - labor market healthy."
        return ""

    def _analyze_stress(self, series_id: str, value: float) -> str:
        """Analyze market stress indicators."""
        if series_id == "VIXCLS":
            if value > 30:
                return "SIGNAL: HIGH volatility - market fear elevated. Consider hedging or reducing exposure."
            elif value > 20:
                return "SIGNAL: Elevated volatility - caution warranted."
            else:
                return "SIGNAL: Low volatility - complacency? Consider tail risk hedges."
        elif series_id == "BAMLH0A0HYM2":
            if value > 5:
                return "SIGNAL: Credit stress ELEVATED - risk-off signal. Favor quality over junk."
            else:
                return "SIGNAL: Credit spreads tight - risk-on environment."
        return ""

    def _analyze_growth(self, series_id: str, value: float) -> str:
        """Analyze growth indicators."""
        if value < 0:
            return "SIGNAL: NEGATIVE growth - recession territory. Favor defensives, bonds."
        elif value < 2:
            return "SIGNAL: Slow growth - monitor for acceleration or deceleration."
        else:
            return "SIGNAL: Healthy growth - supports risk assets."

    def _analyze_consumer(self, series_id: str, value: float) -> str:
        """Analyze consumer indicators."""
        if series_id == "UMCSENT":
            if value < 70:
                return "SIGNAL: Consumer sentiment LOW - spending headwinds. Caution on retail."
            elif value > 90:
                return "SIGNAL: Consumer sentiment HIGH - spending tailwind."
            else:
                return "SIGNAL: Consumer sentiment neutral."
        return ""

    def _format_history(self, observations: list[dict]) -> str:
        """Format observation history."""
        if not observations:
            return "No historical data available."

        lines = []
        for obs in observations[:5]:  # Last 5 readings
            date = obs.get("date", "N/A")
            value = obs.get("value", "N/A")
            lines.append(f"  {date}: {value}")

        return "\n".join(lines)

    def _calculate_sentiment(self, series_id: str, value: float, data: dict[str, Any]) -> float:
        """
        Calculate sentiment score for economic indicator.

        Returns:
            Sentiment score 0-1 (0.5 = neutral)
        """
        # Get historical values for context
        observations = data.get("observations", [])
        if len(observations) < 2:
            return 0.5

        try:
            prev_value = float(observations[1].get("value", 0))
        except (ValueError, TypeError):
            return 0.5

        # Direction of change
        if prev_value == 0:
            return 0.5

        change_pct = ((value - prev_value) / abs(prev_value)) * 100

        # Different indicators have different "good" directions
        positive_up = [
            "GDP",
            "GDPC1",
            "PAYEMS",
            "UMCSENT",
            "RSAFS",
            "INDPRO",
            "HOUST",
        ]
        positive_down = [
            "UNRATE",
            "ICSA",
            "CPIAUCSL",
            "PCEPI",
            "VIXCLS",
            "BAMLH0A0HYM2",
            "TEDRATE",
            "MORTGAGE30US",
        ]

        if series_id in positive_up:
            # Higher is better
            if change_pct > 0.5:
                return min(0.5 + change_pct / 10, 0.9)
            elif change_pct < -0.5:
                return max(0.5 + change_pct / 10, 0.1)
        elif series_id in positive_down:
            # Lower is better
            if change_pct < -0.5:
                return min(0.5 - change_pct / 10, 0.9)
            elif change_pct > 0.5:
                return max(0.5 - change_pct / 10, 0.1)

        return 0.5

    def get_macro_regime(self) -> dict[str, Any]:
        """
        Determine current macro regime from key indicators.

        Returns:
            Regime assessment dict
        """
        if not self.api_key:
            return {"regime": "unknown", "reason": "FRED API not configured"}

        # Fetch key regime indicators
        indicators = {}
        key_series = ["T10Y2Y", "VIXCLS", "BAMLH0A0HYM2", "UNRATE"]

        for series_id in key_series:
            try:
                data = self._fetch_series(
                    series_id,
                    (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
                    datetime.now().strftime("%Y-%m-%d"),
                )
                if data and data.get("latest_value") != ".":
                    indicators[series_id] = float(data["latest_value"])
            except Exception:
                continue

        # Determine regime
        if not indicators:
            return {"regime": "unknown", "reason": "Could not fetch indicators"}

        # Risk-off signals
        risk_off_signals = 0
        if indicators.get("T10Y2Y", 1) < 0:
            risk_off_signals += 2  # Yield curve inversion is strong signal
        if indicators.get("VIXCLS", 15) > 25:
            risk_off_signals += 1
        if indicators.get("BAMLH0A0HYM2", 3) > 5:
            risk_off_signals += 1
        if indicators.get("UNRATE", 4) > 5:
            risk_off_signals += 1

        if risk_off_signals >= 3:
            regime = "risk_off"
            reason = "Multiple stress indicators elevated"
        elif risk_off_signals >= 1:
            regime = "cautious"
            reason = "Some stress signals present"
        else:
            regime = "risk_on"
            reason = "Low stress environment"

        return {
            "regime": regime,
            "reason": reason,
            "indicators": indicators,
            "risk_off_signals": risk_off_signals,
            "timestamp": datetime.now().isoformat(),
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    collector = FREDCollector()

    print("Fetching FRED economic data...")
    articles = collector.collect_market_news(days_back=30)

    print(f"\nCollected {len(articles)} indicators")
    for article in articles[:5]:
        print(f"\n{article['title']}")
        print(f"  Date: {article['published_date']}")
        print(f"  Sentiment: {article.get('sentiment', 'N/A')}")

    print("\n\nMacro Regime Assessment:")
    regime = collector.get_macro_regime()
    print(f"  Regime: {regime['regime']}")
    print(f"  Reason: {regime['reason']}")
