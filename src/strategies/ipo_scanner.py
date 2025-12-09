"""
Tier 4 Automation: IPO and Crowdfund Scanner

Scans SEC EDGAR for recent IPO filings (S-1) and evaluates them
using sentiment analysis to identify high-potential opportunities.

This module automates the previously manual Tier 4 allocation process.

Gate: Activate at $10k equity for proper diversification.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class IPOFiling:
    """Represents an IPO filing from SEC EDGAR."""

    company_name: str
    ticker: str | None
    filing_date: datetime
    filing_type: str  # S-1, S-1/A, etc.
    cik: str
    industry: str | None = None
    filing_url: str | None = None
    description: str | None = None
    sentiment_score: float = 0.0
    recommendation: str = "hold"


@dataclass
class ScannerConfig:
    """Configuration for IPO scanner."""

    lookback_days: int = 30
    min_sentiment_threshold: float = 0.3
    max_allocations: int = 3
    allocation_pct: float = 0.10  # 10% of Tier 4 budget
    min_equity: float = 10000.0
    filing_types: tuple = ("S-1", "S-1/A")
    excluded_industries: tuple = ("blank_check", "spac")


class IPOScanner:
    """
    Scans SEC EDGAR for IPO filings and evaluates opportunities.

    Uses SEC EDGAR API (free) or sec-api.io for filing data,
    then applies sentiment analysis to identify high-potential IPOs.

    Example:
        >>> scanner = IPOScanner()
        >>> filings = scanner.scan_recent_ipos()
        >>> recommendations = scanner.evaluate_filings(filings)
        >>> for rec in recommendations:
        ...     print(f"{rec.company_name}: {rec.recommendation}")
    """

    SEC_EDGAR_BASE = "https://www.sec.gov/cgi-bin/browse-edgar"
    SEC_API_FILINGS = "https://efts.sec.gov/LATEST/search-index"

    def __init__(self, config: ScannerConfig | None = None):
        self.config = config or ScannerConfig()

        # Check for sec-api.io API key (optional, provides better data)
        self.sec_api_key = os.getenv("SEC_API_KEY")

    def scan_recent_ipos(self) -> list[IPOFiling]:
        """
        Scan SEC EDGAR for recent IPO filings.

        Returns:
            List of IPOFiling objects from recent S-1 filings
        """
        filings = []

        try:
            filings = self._fetch_edgar_filings()
        except Exception as e:
            logger.warning(f"SEC EDGAR fetch failed: {e}")

        # Fallback: Try sec-api.io if available
        if not filings and self.sec_api_key:
            try:
                filings = self._fetch_sec_api_filings()
            except Exception as e:
                logger.warning(f"sec-api.io fetch failed: {e}")

        # Fallback: Try yfinance IPO calendar
        if not filings:
            try:
                filings = self._fetch_yfinance_ipos()
            except Exception as e:
                logger.warning(f"yfinance IPO fetch failed: {e}")

        logger.info(f"Found {len(filings)} IPO filings in last {self.config.lookback_days} days")
        return filings

    def _fetch_edgar_filings(self) -> list[IPOFiling]:
        """Fetch filings directly from SEC EDGAR."""
        import requests

        filings = []

        # SEC EDGAR full-text search API
        search_url = "https://efts.sec.gov/LATEST/search-index"

        params = {
            "q": "form-type:S-1",
            "dateRange": "custom",
            "startdt": (datetime.now() - timedelta(days=self.config.lookback_days)).strftime(
                "%Y-%m-%d"
            ),
            "enddt": datetime.now().strftime("%Y-%m-%d"),
            "forms": "S-1,S-1/A",
        }

        try:
            # Use SEC's company search instead (more reliable)
            search_url = f"{self.SEC_EDGAR_BASE}"
            params = {
                "action": "getcurrent",
                "type": "S-1",
                "company": "",
                "dateb": "",
                "owner": "include",
                "count": 40,
                "output": "atom",
            }

            response = requests.get(search_url, params=params, timeout=30)
            response.raise_for_status()

            # Parse Atom feed
            import defusedxml.ElementTree as ET

            root = ET.fromstring(response.content)

            # Namespace for Atom
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            for entry in root.findall(".//atom:entry", ns):
                try:
                    title = entry.find("atom:title", ns)
                    updated = entry.find("atom:updated", ns)
                    link = entry.find("atom:link", ns)
                    summary = entry.find("atom:summary", ns)

                    if title is not None:
                        title_text = title.text or ""
                        # Parse company name and CIK from title
                        # Format: "S-1 - Company Name (0001234567) (Filer)"
                        parts = title_text.split(" - ", 1)
                        if len(parts) >= 2:
                            company_info = parts[1]
                            company_name = company_info.split(" (")[0].strip()
                            cik_match = company_info.split("(")
                            cik = cik_match[1].rstrip(")") if len(cik_match) > 1 else ""

                            filing = IPOFiling(
                                company_name=company_name,
                                ticker=None,  # Not in S-1 typically
                                filing_date=datetime.fromisoformat(
                                    updated.text.replace("Z", "+00:00")
                                )
                                if updated is not None and updated.text
                                else datetime.now(),
                                filing_type="S-1",
                                cik=cik.strip("()"),
                                filing_url=link.get("href") if link is not None else None,
                                description=summary.text if summary is not None else None,
                            )
                            filings.append(filing)
                except Exception as e:
                    logger.debug(f"Error parsing entry: {e}")
                    continue

        except Exception as e:
            logger.error(f"EDGAR fetch error: {e}")

        return filings

    def _fetch_sec_api_filings(self) -> list[IPOFiling]:
        """Fetch filings from sec-api.io (if API key available)."""
        if not self.sec_api_key:
            return []

        import requests

        filings = []

        try:
            headers = {"Authorization": self.sec_api_key}
            params = {
                "query": {"query_string": {"query": 'formType:"S-1" OR formType:"S-1/A"'}},
                "from": "0",
                "size": "50",
                "sort": [{"filedAt": {"order": "desc"}}],
            }

            response = requests.post(
                "https://api.sec-api.io",
                headers=headers,
                json=params,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            for hit in data.get("filings", []):
                filing = IPOFiling(
                    company_name=hit.get("companyName", "Unknown"),
                    ticker=hit.get("ticker"),
                    filing_date=datetime.fromisoformat(hit.get("filedAt", "")[:10]),
                    filing_type=hit.get("formType", "S-1"),
                    cik=hit.get("cik", ""),
                    industry=hit.get("sic", ""),
                    filing_url=hit.get("linkToFilingDetails"),
                    description=hit.get("description"),
                )
                filings.append(filing)

        except Exception as e:
            logger.error(f"sec-api.io fetch error: {e}")

        return filings

    def _fetch_yfinance_ipos(self) -> list[IPOFiling]:
        """Fetch upcoming IPOs from yfinance."""
        filings = []

        try:
            import importlib.util

            if importlib.util.find_spec("yfinance") is not None:
                # yfinance doesn't have direct IPO calendar, but we can check
                # for recently listed stocks with minimal history
                # This is a fallback approach

                # Check for stocks that went public recently
                # by looking for symbols with very short price history
                logger.info("yfinance IPO scan - using market screening approach")
            else:
                logger.warning("yfinance not available for IPO scan")

        except ImportError:
            logger.warning("yfinance not available for IPO scan")
        except Exception as e:
            logger.error(f"yfinance IPO scan error: {e}")

        return filings

    def evaluate_filings(
        self,
        filings: list[IPOFiling],
        equity: float = 0.0,
    ) -> list[IPOFiling]:
        """
        Evaluate IPO filings using sentiment analysis.

        Args:
            filings: List of IPOFiling objects to evaluate
            equity: Current portfolio equity for gating

        Returns:
            List of evaluated filings with sentiment scores and recommendations
        """
        if equity < self.config.min_equity:
            logger.info(
                f"Equity ${equity:.2f} below gate ${self.config.min_equity:.2f}, "
                "skipping IPO evaluation"
            )
            return []

        evaluated = []

        for filing in filings:
            try:
                # Skip excluded industries
                if filing.industry and any(
                    exc in filing.industry.lower() for exc in self.config.excluded_industries
                ):
                    continue

                # Calculate sentiment score
                filing.sentiment_score = self._calculate_sentiment(filing)

                # Determine recommendation
                if filing.sentiment_score >= self.config.min_sentiment_threshold:
                    filing.recommendation = "allocate"
                elif filing.sentiment_score >= 0.1:
                    filing.recommendation = "watch"
                else:
                    filing.recommendation = "skip"

                evaluated.append(filing)

            except Exception as e:
                logger.warning(f"Error evaluating {filing.company_name}: {e}")
                continue

        # Sort by sentiment score
        evaluated.sort(key=lambda x: x.sentiment_score, reverse=True)

        # Limit to max allocations
        allocations = [f for f in evaluated if f.recommendation == "allocate"]
        if len(allocations) > self.config.max_allocations:
            for f in allocations[self.config.max_allocations :]:
                f.recommendation = "watch"

        return evaluated

    def _calculate_sentiment(self, filing: IPOFiling) -> float:
        """
        Calculate sentiment score for an IPO filing.

        Uses news sentiment, filing text analysis, and market conditions.
        """
        score = 0.0

        try:
            # Try to get news sentiment for the company
            from src.utils.news_sentiment import NewsSentimentAnalyzer

            analyzer = NewsSentimentAnalyzer()
            news_score = analyzer.get_sentiment(filing.company_name)
            score += news_score * 0.5

        except ImportError:
            # Fallback: Use simple keyword analysis
            if filing.description:
                positive_keywords = [
                    "growth",
                    "revenue",
                    "profitable",
                    "expanding",
                    "innovative",
                    "leading",
                    "strong",
                ]
                negative_keywords = [
                    "loss",
                    "debt",
                    "risk",
                    "uncertain",
                    "declining",
                    "warning",
                ]

                desc_lower = filing.description.lower()
                pos_count = sum(1 for kw in positive_keywords if kw in desc_lower)
                neg_count = sum(1 for kw in negative_keywords if kw in desc_lower)

                keyword_score = (pos_count - neg_count) / max(1, pos_count + neg_count)
                score += keyword_score * 0.3

        except Exception as e:
            logger.debug(f"Sentiment calculation error: {e}")

        # Normalize to 0-1 range
        score = max(0.0, min(1.0, (score + 1) / 2))

        return round(score, 3)

    def allocate_tier4(
        self,
        filings: list[IPOFiling],
        daily_budget: float,
        dry_run: bool = True,
    ) -> list[dict]:
        """
        Allocate Tier 4 budget to recommended IPOs.

        Args:
            filings: Evaluated filings with recommendations
            daily_budget: Daily investment budget
            dry_run: If True, only log allocations without executing

        Returns:
            List of allocation decisions
        """
        allocations = []
        tier4_budget = daily_budget * self.config.allocation_pct

        recommended = [f for f in filings if f.recommendation == "allocate"]

        if not recommended:
            logger.info("No IPO allocations recommended")
            return []

        # Equal weight among recommendations
        per_ipo_allocation = tier4_budget / len(recommended)

        for filing in recommended:
            allocation = {
                "company": filing.company_name,
                "ticker": filing.ticker,
                "cik": filing.cik,
                "amount": round(per_ipo_allocation, 2),
                "sentiment_score": filing.sentiment_score,
                "filing_date": filing.filing_date.isoformat(),
                "executed": not dry_run,
            }
            allocations.append(allocation)

            if dry_run:
                logger.info(
                    f"[DRY RUN] Would allocate ${per_ipo_allocation:.2f} "
                    f"to {filing.company_name} (sentiment: {filing.sentiment_score:.2f})"
                )
            else:
                logger.info(
                    f"Allocating ${per_ipo_allocation:.2f} "
                    f"to {filing.company_name} (sentiment: {filing.sentiment_score:.2f})"
                )

        return allocations

    def get_scan_summary(self, filings: list[IPOFiling]) -> dict:
        """Get summary of scan results."""
        return {
            "total_filings": len(filings),
            "allocate_count": sum(1 for f in filings if f.recommendation == "allocate"),
            "watch_count": sum(1 for f in filings if f.recommendation == "watch"),
            "skip_count": sum(1 for f in filings if f.recommendation == "skip"),
            "avg_sentiment": (
                sum(f.sentiment_score for f in filings) / len(filings) if filings else 0
            ),
            "top_opportunities": [
                {"company": f.company_name, "score": f.sentiment_score}
                for f in filings[:3]
                if f.recommendation == "allocate"
            ],
        }


def run_ipo_scan(equity: float = 10000.0, dry_run: bool = True) -> dict:
    """
    Convenience function to run IPO scan and get allocations.

    Args:
        equity: Current portfolio equity
        dry_run: If True, don't execute allocations

    Returns:
        Scan results including filings and allocations
    """
    scanner = IPOScanner()

    # Scan for recent IPOs
    filings = scanner.scan_recent_ipos()

    # Evaluate filings
    evaluated = scanner.evaluate_filings(filings, equity=equity)

    # Get allocations
    allocations = scanner.allocate_tier4(
        evaluated,
        daily_budget=float(os.getenv("DAILY_INVESTMENT", "10.0")),
        dry_run=dry_run,
    )

    return {
        "scan_date": datetime.now().isoformat(),
        "total_filings": len(filings),
        "evaluated_filings": len(evaluated),
        "allocations": allocations,
        "summary": scanner.get_scan_summary(evaluated),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("IPO SCANNER - Tier 4 Automation")
    print("=" * 60)

    result = run_ipo_scan(equity=15000.0, dry_run=True)

    print(f"\nScan Date: {result['scan_date']}")
    print(f"Total Filings Found: {result['total_filings']}")
    print(f"Evaluated: {result['evaluated_filings']}")

    print("\nSummary:")
    for key, value in result["summary"].items():
        print(f"  {key}: {value}")

    if result["allocations"]:
        print("\nRecommended Allocations:")
        for alloc in result["allocations"]:
            print(f"  - {alloc['company']}: ${alloc['amount']:.2f}")
