"""
SEC 13F Filing Collector

Monitors institutional investor holdings via SEC EDGAR 13F filings.
Essential for understanding smart money positioning.

Key Features:
- Tracks major institutional investors (hedge funds, mutual funds, etc.)
- Monitors position changes (new buys, sells, increases, decreases)
- Identifies unusual activity and conviction bets
- Calculates institutional ownership percentages

API: SEC EDGAR (free, no key required)
Data Delay: 13F filings are due 45 days after quarter end

Author: Trading System
Created: 2025-12-01
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Any
from xml.etree import ElementTree

import requests

from src.rag.collectors.base_collector import BaseNewsCollector

logger = logging.getLogger(__name__)


# Major institutional investors to track (CIK numbers)
TRACKED_INSTITUTIONS = {
    "0001067983": {"name": "Berkshire Hathaway", "type": "conglomerate"},
    "0001336528": {"name": "Bridgewater Associates", "type": "hedge_fund"},
    "0001350694": {"name": "Renaissance Technologies", "type": "quant_fund"},
    "0001037389": {"name": "Vanguard Group", "type": "asset_manager"},
    "0000315066": {"name": "BlackRock", "type": "asset_manager"},
    "0001061768": {"name": "State Street", "type": "asset_manager"},
    "0001166559": {"name": "Citadel Advisors", "type": "hedge_fund"},
    "0001079114": {"name": "Two Sigma", "type": "quant_fund"},
    "0001365389": {"name": "Millennium Management", "type": "hedge_fund"},
    "0001029160": {"name": "DE Shaw", "type": "quant_fund"},
    "0001649339": {"name": "Tiger Global", "type": "hedge_fund"},
    "0001536411": {"name": "Viking Global", "type": "hedge_fund"},
    "0001535392": {"name": "Lone Pine Capital", "type": "hedge_fund"},
    "0001325256": {"name": "Pershing Square", "type": "activist"},
    "0001418814": {"name": "Third Point", "type": "activist"},
    "0001061165": {"name": "Druckenmiller", "type": "macro"},
    "0001510387": {"name": "Appaloosa", "type": "hedge_fund"},
    "0001541617": {"name": "Baupost Group", "type": "value"},
    "0000902219": {"name": "Greenlight Capital", "type": "value"},
    "0001103804": {"name": "Elliott Management", "type": "activist"},
}


class SEC13FCollector(BaseNewsCollector):
    """
    Collector for SEC 13F institutional holdings filings.

    Tracks what the smart money is buying and selling.
    """

    EDGAR_BASE = "https://www.sec.gov"
    EDGAR_API = "https://data.sec.gov"

    def __init__(self):
        """Initialize SEC 13F collector."""
        super().__init__(source_name="sec13f")

        # Headers required by SEC (they block default user-agents)
        self.headers = {
            "User-Agent": "TradingSystem/1.0 (research@example.com)",
            "Accept": "application/json",
        }

        # Cache for filings
        self._filing_cache: dict[str, dict] = {}

    def collect_ticker_news(self, ticker: str, days_back: int = 90) -> list[dict[str, Any]]:
        """
        Collect institutional activity for a specific ticker.

        Args:
            ticker: Stock ticker symbol
            days_back: Days to look back (13F filings are quarterly)

        Returns:
            List of institutional activity articles
        """
        articles = []

        # Search for filings mentioning this ticker
        for cik, institution in TRACKED_INSTITUTIONS.items():
            try:
                holdings = self._get_institution_holdings(cik)
                if not holdings:
                    continue

                # Find this ticker in holdings
                ticker_holdings = [h for h in holdings if self._match_ticker(h, ticker)]

                if ticker_holdings:
                    article = self._create_ticker_article(ticker, institution, ticker_holdings)
                    if article:
                        articles.append(article)

            except Exception as e:
                logger.debug(f"Error processing {institution['name']}: {e}")
                continue

        logger.info(f"Found {len(articles)} institutional activities for {ticker}")
        return articles

    def collect_market_news(self, days_back: int = 45) -> list[dict[str, Any]]:
        """
        Collect recent 13F filings from tracked institutions.

        Args:
            days_back: Days to look back

        Returns:
            List of filing articles
        """
        articles = []

        for cik, institution in TRACKED_INSTITUTIONS.items():
            try:
                # Get recent filings
                filings = self._get_recent_filings(cik, "13F-HR", days_back)

                for filing in filings[:1]:  # Just most recent
                    article = self._create_filing_article(cik, institution, filing)
                    if article:
                        articles.append(article)

            except Exception as e:
                logger.debug(f"Error fetching {institution['name']}: {e}")
                continue

        logger.info(f"Collected {len(articles)} institutional filing summaries")
        return articles

    def _get_recent_filings(self, cik: str, form_type: str, days_back: int) -> list[dict]:
        """
        Get recent filings for an institution.

        Args:
            cik: SEC CIK number
            form_type: Form type (e.g., "13F-HR")
            days_back: Days to look back

        Returns:
            List of filing metadata
        """
        url = f"{self.EDGAR_API}/submissions/CIK{cik.zfill(10)}.json"

        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            filings = []
            recent_filings = data.get("filings", {}).get("recent", {})

            forms = recent_filings.get("form", [])
            dates = recent_filings.get("filingDate", [])
            accessions = recent_filings.get("accessionNumber", [])

            cutoff_date = datetime.now() - timedelta(days=days_back)

            for i, form in enumerate(forms):
                if form == form_type and i < len(dates) and i < len(accessions):
                    filing_date = datetime.strptime(dates[i], "%Y-%m-%d")
                    if filing_date >= cutoff_date:
                        filings.append(
                            {
                                "form": form,
                                "date": dates[i],
                                "accession": accessions[i],
                            }
                        )

            return filings

        except requests.RequestException as e:
            logger.debug(f"Error fetching filings for CIK {cik}: {e}")
            return []

    def _get_institution_holdings(self, cik: str) -> list[dict] | None:
        """
        Get current holdings for an institution from most recent 13F.

        Args:
            cik: SEC CIK number

        Returns:
            List of holdings or None
        """
        # Check cache first
        cache_key = f"{cik}_holdings"
        if cache_key in self._filing_cache:
            cached = self._filing_cache[cache_key]
            if datetime.now() - cached["timestamp"] < timedelta(hours=24):
                return cached["holdings"]

        # Get most recent 13F
        filings = self._get_recent_filings(cik, "13F-HR", 120)
        if not filings:
            return None

        latest = filings[0]
        accession = latest["accession"].replace("-", "")

        # Fetch the information table
        url = f"{self.EDGAR_BASE}/Archives/edgar/data/{cik.lstrip('0')}/{accession}/infotable.xml"

        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            if response.status_code != 200:
                # Try alternative filename
                url = url.replace("infotable.xml", "primary_doc.xml")
                response = requests.get(url, headers=self.headers, timeout=15)

            if response.status_code != 200:
                return None

            holdings = self._parse_13f_xml(response.text)

            # Cache results
            self._filing_cache[cache_key] = {
                "holdings": holdings,
                "timestamp": datetime.now(),
            }

            return holdings

        except Exception as e:
            logger.debug(f"Error fetching holdings for CIK {cik}: {e}")
            return None

    def _parse_13f_xml(self, xml_content: str) -> list[dict]:
        """
        Parse 13F XML information table.

        Args:
            xml_content: Raw XML content

        Returns:
            List of parsed holdings
        """
        holdings = []

        try:
            # Handle namespace
            xml_content = re.sub(r'xmlns="[^"]+"', "", xml_content)
            root = ElementTree.fromstring(xml_content)

            for info_table in root.iter():
                if "infoTable" in info_table.tag:
                    holding = {}

                    for child in info_table:
                        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

                        if tag == "nameOfIssuer":
                            holding["name"] = child.text
                        elif tag == "titleOfClass":
                            holding["title"] = child.text
                        elif tag == "cusip":
                            holding["cusip"] = child.text
                        elif tag == "value":
                            try:
                                # Value is in thousands
                                holding["value"] = int(child.text) * 1000
                            except (ValueError, TypeError):
                                holding["value"] = 0
                        elif tag == "sshPrnamt":
                            try:
                                holding["shares"] = int(child.text)
                            except (ValueError, TypeError):
                                holding["shares"] = 0
                        elif tag == "putCall":
                            holding["put_call"] = child.text

                    if holding.get("name"):
                        holdings.append(holding)

        except ElementTree.ParseError as e:
            logger.debug(f"XML parsing error: {e}")

        return holdings

    def _match_ticker(self, holding: dict, ticker: str) -> bool:
        """
        Check if a holding matches a ticker.

        Args:
            holding: Holding dict
            ticker: Ticker to match

        Returns:
            True if matches
        """
        name = holding.get("name", "").upper()
        ticker = ticker.upper()

        # Common mappings
        ticker_to_name = {
            "AAPL": "APPLE",
            "MSFT": "MICROSOFT",
            "GOOGL": "ALPHABET",
            "GOOG": "ALPHABET",
            "AMZN": "AMAZON",
            "META": "META PLATFORMS",
            "FB": "META PLATFORMS",
            "NVDA": "NVIDIA",
            "TSLA": "TESLA",
            "BRK.A": "BERKSHIRE",
            "BRK.B": "BERKSHIRE",
            "JPM": "JPMORGAN",
            "V": "VISA",
            "JNJ": "JOHNSON",
            "WMT": "WALMART",
            "PG": "PROCTER",
            "UNH": "UNITEDHEALTH",
            "HD": "HOME DEPOT",
            "MA": "MASTERCARD",
            "DIS": "WALT DISNEY",
            "PYPL": "PAYPAL",
            "NFLX": "NETFLIX",
            "ADBE": "ADOBE",
            "CRM": "SALESFORCE",
            "INTC": "INTEL",
            "AMD": "ADVANCED MICRO",
            "QCOM": "QUALCOMM",
            "TXN": "TEXAS INSTRUMENTS",
            "AVGO": "BROADCOM",
            "COST": "COSTCO",
            "PEP": "PEPSICO",
            "KO": "COCA-COLA",
        }

        search_term = ticker_to_name.get(ticker, ticker)
        return search_term in name or ticker in name

    def _create_ticker_article(
        self,
        ticker: str,
        institution: dict,
        holdings: list[dict],
    ) -> dict[str, Any] | None:
        """Create article for ticker-specific institutional holdings."""
        if not holdings:
            return None

        total_value = sum(h.get("value", 0) for h in holdings)
        total_shares = sum(h.get("shares", 0) for h in holdings)

        content = f"""Institutional Holding: {institution["name"]} ({institution["type"]})
Ticker: {ticker}

Position Summary:
- Total Value: ${total_value:,.0f}
- Total Shares: {total_shares:,}
- Number of Classes: {len(holdings)}

Holdings Detail:
"""
        for h in holdings:
            content += f"  - {h.get('name', 'N/A')}: {h.get('shares', 0):,} shares (${h.get('value', 0):,.0f})\n"
            if h.get("put_call"):
                content += f"    Type: {h.get('put_call')}\n"

        content += """
Trading Signal:
Major institutional ownership signals validation of investment thesis.
Monitor quarterly changes for buying/selling pressure.
"""

        return self.normalize_article(
            title=f"{institution['name']} holds ${total_value:,.0f} in {ticker}",
            content=content,
            url=f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={institution.get('cik', '')}&type=13F",
            published_date=datetime.now().strftime("%Y-%m-%d"),
            ticker=ticker,
            sentiment=0.6 if total_value > 1000000000 else 0.55,  # Large positions = conviction
        )

    def _create_filing_article(
        self,
        cik: str,
        institution: dict,
        filing: dict,
    ) -> dict[str, Any] | None:
        """Create article summarizing an institution's 13F filing."""
        holdings = self._get_institution_holdings(cik)
        if not holdings:
            return None

        # Calculate summary stats
        total_value = sum(h.get("value", 0) for h in holdings)
        num_positions = len(holdings)

        # Top holdings
        sorted_holdings = sorted(holdings, key=lambda x: x.get("value", 0), reverse=True)
        top_5 = sorted_holdings[:5]

        content = f"""13F Filing Summary: {institution["name"]}
Filing Date: {filing["date"]}
Institution Type: {institution["type"]}

Portfolio Overview:
- Total Portfolio Value: ${total_value:,.0f}
- Number of Positions: {num_positions}

Top 5 Holdings:
"""
        for i, h in enumerate(top_5, 1):
            pct = (h.get("value", 0) / total_value * 100) if total_value > 0 else 0
            content += f"{i}. {h.get('name', 'N/A')}: ${h.get('value', 0):,.0f} ({pct:.1f}%)\n"

        content += f"""
Investment Style Analysis:
Based on holdings concentration and position sizes, this appears to be a
{self._analyze_portfolio_style(holdings, institution)} portfolio.

Sector Exposure:
{self._estimate_sector_exposure(holdings)}
"""

        return self.normalize_article(
            title=f"{institution['name']} 13F Filing: ${total_value / 1e9:.1f}B Portfolio",
            content=content,
            url=f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=13F-HR",
            published_date=filing["date"],
            ticker="INST",  # Institutional data marker
            sentiment=0.5,  # Neutral - informational
        )

    def _analyze_portfolio_style(self, holdings: list[dict], institution: dict) -> str:
        """Analyze portfolio concentration and style."""
        if not holdings:
            return "unknown"

        total_value = sum(h.get("value", 0) for h in holdings)
        if total_value == 0:
            return "unknown"

        # Top 10 concentration
        sorted_holdings = sorted(holdings, key=lambda x: x.get("value", 0), reverse=True)
        top_10_value = sum(h.get("value", 0) for h in sorted_holdings[:10])
        concentration = top_10_value / total_value

        if concentration > 0.7:
            style = "highly concentrated"
        elif concentration > 0.5:
            style = "concentrated"
        else:
            style = "diversified"

        return f"{style} {institution['type']}"

    def _estimate_sector_exposure(self, holdings: list[dict]) -> str:
        """Estimate sector exposure from holding names."""
        # Simple keyword-based sector classification
        sectors = {
            "Technology": 0,
            "Healthcare": 0,
            "Financial": 0,
            "Consumer": 0,
            "Energy": 0,
            "Industrial": 0,
            "Other": 0,
        }

        tech_keywords = [
            "APPLE",
            "MICROSOFT",
            "GOOGLE",
            "ALPHABET",
            "NVIDIA",
            "META",
            "AMAZON",
            "ADOBE",
            "SALESFORCE",
            "ORACLE",
            "INTEL",
            "AMD",
            "BROADCOM",
            "QUALCOMM",
        ]
        health_keywords = [
            "PFIZER",
            "JOHNSON",
            "UNITEDHEALTH",
            "MERCK",
            "LILLY",
            "ABBVIE",
            "BRISTOL",
            "AMGEN",
            "GILEAD",
            "REGENERON",
        ]
        finance_keywords = [
            "JPMORGAN",
            "BANK",
            "GOLDMAN",
            "MORGAN STANLEY",
            "WELLS",
            "VISA",
            "MASTERCARD",
            "BERKSHIRE",
            "BLACKROCK",
        ]
        consumer_keywords = [
            "WALMART",
            "COSTCO",
            "HOME DEPOT",
            "NIKE",
            "MCDONALD",
            "STARBUCKS",
            "COCA-COLA",
            "PEPSI",
            "PROCTER",
            "DISNEY",
        ]
        energy_keywords = [
            "EXXON",
            "CHEVRON",
            "CONOCOPHILLIPS",
            "SCHLUMBERGER",
            "OCCIDENTAL",
            "PIONEER",
        ]
        industrial_keywords = [
            "CATERPILLAR",
            "DEERE",
            "BOEING",
            "LOCKHEED",
            "RAYTHEON",
            "HONEYWELL",
            "3M",
            "UNION PACIFIC",
        ]

        for h in holdings:
            name = h.get("name", "").upper()
            value = h.get("value", 0)

            if any(kw in name for kw in tech_keywords):
                sectors["Technology"] += value
            elif any(kw in name for kw in health_keywords):
                sectors["Healthcare"] += value
            elif any(kw in name for kw in finance_keywords):
                sectors["Financial"] += value
            elif any(kw in name for kw in consumer_keywords):
                sectors["Consumer"] += value
            elif any(kw in name for kw in energy_keywords):
                sectors["Energy"] += value
            elif any(kw in name for kw in industrial_keywords):
                sectors["Industrial"] += value
            else:
                sectors["Other"] += value

        total = sum(sectors.values())
        if total == 0:
            return "Unable to estimate sector exposure"

        # Format output
        lines = []
        for sector, value in sorted(sectors.items(), key=lambda x: x[1], reverse=True):
            if value > 0:
                pct = value / total * 100
                lines.append(f"  {sector}: {pct:.1f}%")

        return "\n".join(lines[:5])  # Top 5 sectors

    def get_top_holdings_summary(self) -> list[dict[str, Any]]:
        """
        Get summary of top holdings across tracked institutions.

        Returns:
            List of most commonly held stocks with institutional counts
        """
        holdings_count: dict[str, dict] = {}

        for cik, institution in TRACKED_INSTITUTIONS.items():
            try:
                holdings = self._get_institution_holdings(cik)
                if not holdings:
                    continue

                for h in holdings[:50]:  # Top 50 per institution
                    name = h.get("name", "").upper()
                    if name not in holdings_count:
                        holdings_count[name] = {
                            "name": name,
                            "institutions": [],
                            "total_value": 0,
                        }
                    holdings_count[name]["institutions"].append(institution["name"])
                    holdings_count[name]["total_value"] += h.get("value", 0)

            except Exception as e:
                logger.debug(f"Error processing {institution['name']}: {e}")
                continue

        # Sort by number of institutions holding
        sorted_holdings = sorted(
            holdings_count.values(),
            key=lambda x: (len(x["institutions"]), x["total_value"]),
            reverse=True,
        )

        return sorted_holdings[:20]  # Top 20 most widely held


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    collector = SEC13FCollector()

    print("Fetching 13F filings from major institutions...")
    articles = collector.collect_market_news(days_back=90)

    print(f"\nCollected {len(articles)} filing summaries")
    for article in articles[:3]:
        print(f"\n{article['title']}")
        print(f"  Date: {article['published_date']}")

    print("\n\nTop Holdings Across Institutions:")
    top = collector.get_top_holdings_summary()
    for holding in top[:10]:
        print(
            f"  {holding['name']}: {len(holding['institutions'])} institutions, "
            f"${holding['total_value'] / 1e9:.1f}B total"
        )
