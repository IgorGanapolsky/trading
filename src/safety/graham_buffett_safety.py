"""
Graham-Buffett Investment Safety Module

Implements core investment principles from Benjamin Graham's "The Intelligent Investor" and Warren Buffett:
1. Margin of Safety - Only buy when price is significantly below intrinsic value
2. Quality Companies - Screen for strong fundamentals (low debt, consistent earnings)
3. Circle of Competence - Focus on well-known, understandable businesses
4. Long-term Perspective - Reduce trading frequency, hold quality positions
5. Emotional Discipline - Avoid buying at peaks, wait for pullbacks (Mr. Market concept)
6. Diversification - Proper position sizing and diversification limits
7. Defensive Investor Criteria - P/E ratios, P/B ratios, dividend yield
8. Value Investing - Focus on intrinsic value vs market price
9. Dollar-Cost Averaging - Systematic investment approach
10. Rebalancing Discipline - Rebalance based on value, not just momentum

Author: Trading System
Date: 2025-11-24
Enhanced: Added Intelligent Investor principles
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

import yfinance as yf

from src.utils.dcf_valuation import get_global_dcf_calculator

logger = logging.getLogger(__name__)


class SafetyRating(Enum):
    """Safety rating for investment opportunities."""

    EXCELLENT = "excellent"  # Strong margin of safety, high quality
    GOOD = "good"  # Adequate margin of safety, good quality
    ACCEPTABLE = "acceptable"  # Minimal margin of safety, acceptable quality
    POOR = "poor"  # No margin of safety or low quality
    REJECT = "reject"  # Fails safety criteria


@dataclass
class CompanyQuality:
    """Container for company quality metrics."""

    symbol: str
    debt_to_equity: Optional[float]  # Lower is better
    current_ratio: Optional[float]  # Higher is better (>1.0 is healthy)
    roe: Optional[float]  # Return on equity (higher is better)
    roa: Optional[float]  # Return on assets (higher is better)
    profit_margin: Optional[float]  # Net profit margin (higher is better)
    earnings_growth_3y: Optional[float]  # 3-year earnings growth
    earnings_consistency: float  # 0-1 score (1 = very consistent)
    quality_score: float  # 0-100 composite quality score
    # Intelligent Investor additions
    pe_ratio: Optional[float]  # Price-to-earnings ratio
    pb_ratio: Optional[float]  # Price-to-book ratio
    dividend_yield: Optional[float]  # Dividend yield percentage
    market_cap: Optional[float]  # Market capitalization
    timestamp: datetime


@dataclass
class SafetyAnalysis:
    """Complete safety analysis for an investment opportunity."""

    symbol: str
    market_price: float
    intrinsic_value: Optional[float]
    margin_of_safety_pct: Optional[float]  # Positive = discount, negative = premium
    quality: Optional[CompanyQuality]
    safety_rating: SafetyRating
    reasons: list[str]  # Reasons for rating
    warnings: list[str]  # Warning messages
    # Intelligent Investor additions
    defensive_investor_score: Optional[float]  # 0-100 score for defensive investor criteria
    mr_market_sentiment: Optional[str]  # "fearful", "greedy", "neutral" - Mr. Market concept
    value_score: Optional[float]  # 0-100 value investing score
    timestamp: datetime


class GrahamBuffettSafety:
    """
    Implements Graham-Buffett investment safety principles.

    Key Features:
    - Margin of Safety: Requires 20%+ discount to intrinsic value
    - Quality Screening: Filters for strong fundamentals
    - Circle of Competence: Focuses on well-known companies
    - Long-term Focus: Reduces trading frequency
    - Emotional Discipline: Avoids buying at peaks
    """

    # Margin of Safety Thresholds (Graham recommended 50%, we use 20% minimum)
    MIN_MARGIN_OF_SAFETY = 0.20  # 20% minimum discount required
    IDEAL_MARGIN_OF_SAFETY = 0.30  # 30% ideal discount (Graham's preference)

    # Quality Thresholds (Buffett's criteria)
    MAX_DEBT_TO_EQUITY = 0.50  # Maximum 50% debt-to-equity ratio
    MIN_CURRENT_RATIO = 1.0  # Minimum current ratio (liquidity)
    MIN_ROE = 0.10  # Minimum 10% return on equity
    MIN_ROA = 0.05  # Minimum 5% return on assets
    MIN_PROFIT_MARGIN = 0.10  # Minimum 10% net profit margin
    MIN_EARNINGS_GROWTH = 0.05  # Minimum 5% annual earnings growth

    # Intelligent Investor - Defensive Investor Criteria (Graham's checklist)
    MAX_PE_RATIO = 15.0  # Maximum P/E ratio for defensive investor (Graham recommended <15)
    MAX_PB_RATIO = 1.5  # Maximum P/B ratio for defensive investor (Graham recommended <1.5)
    MIN_DIVIDEND_YIELD = 0.02  # Minimum 2% dividend yield (preferred for defensive investor)
    MAX_PE_RATIO_STRICT = 20.0  # Absolute maximum P/E (reject if above)
    MAX_PB_RATIO_STRICT = 2.0  # Absolute maximum P/B (reject if above)

    # Circle of Competence - Well-known, understandable companies
    # Focus on large-cap, established companies
    MIN_MARKET_CAP = 1_000_000_000  # $1B minimum market cap
    ESTABLISHED_COMPANIES_ONLY = True  # Only invest in established companies

    # Well-known tickers (circle of competence)
    # These are companies most investors understand
    WELL_KNOWN_TICKERS = {
        # Tech
        "AAPL",
        "MSFT",
        "GOOGL",
        "GOOG",
        "AMZN",
        "META",
        "NVDA",
        "TSLA",
        # Finance
        "JPM",
        "BAC",
        "WFC",
        "GS",
        "MS",
        # Consumer
        "WMT",
        "HD",
        "MCD",
        "SBUX",
        "NKE",
        "DIS",
        # Healthcare
        "JNJ",
        "PFE",
        "UNH",
        "ABBV",
        # Industrial
        "BA",
        "CAT",
        "GE",
        "HON",
        # Energy
        "XOM",
        "CVX",
        # ETFs (always acceptable)
        "SPY",
        "QQQ",
        "VOO",
        "VTI",
        "DIA",
        "IWM",
    }

    def __init__(
        self,
        min_margin_of_safety: float = MIN_MARGIN_OF_SAFETY,
        require_quality_screening: bool = True,
        require_circle_of_competence: bool = True,
    ):
        """
        Initialize Graham-Buffett Safety Module.

        Args:
            min_margin_of_safety: Minimum margin of safety required (default: 20%)
            require_quality_screening: Whether to require quality screening (default: True)
            require_circle_of_competence: Whether to enforce circle of competence (default: True)
        """
        self.min_margin_of_safety = min_margin_of_safety
        self.require_quality_screening = require_quality_screening
        self.require_circle_of_competence = require_circle_of_competence

        self.dcf_calculator = get_global_dcf_calculator()

        logger.info(
            f"Graham-Buffett Safety Module initialized: "
            f"min_margin_of_safety={min_margin_of_safety * 100:.1f}%, "
            f"quality_screening={require_quality_screening}, "
            f"circle_of_competence={require_circle_of_competence}"
        )

    def analyze_safety(
        self,
        symbol: str,
        market_price: float,
        force_refresh: bool = False,
    ) -> SafetyAnalysis:
        """
        Perform comprehensive safety analysis using Graham-Buffett principles.

        Args:
            symbol: Stock ticker symbol
            market_price: Current market price
            force_refresh: Force refresh of DCF calculation

        Returns:
            SafetyAnalysis with rating and detailed reasons
        """
        symbol = symbol.upper().strip()
        logger.info(f"Analyzing safety for {symbol} at ${market_price:.2f}")

        reasons = []
        warnings = []
        safety_rating = SafetyRating.REJECT

        # Step 1: Circle of Competence Check
        if self.require_circle_of_competence:
            if not self._is_in_circle_of_competence(symbol):
                reasons.append(
                    f"{symbol} not in circle of competence - "
                    f"focusing on well-known, understandable companies"
                )
                return SafetyAnalysis(
                    symbol=symbol,
                    market_price=market_price,
                    intrinsic_value=None,
                    margin_of_safety_pct=None,
                    quality=None,
                    safety_rating=SafetyRating.REJECT,
                    reasons=reasons,
                    warnings=warnings,
                    timestamp=datetime.now(),
                )

        # Step 2: Calculate Intrinsic Value (Margin of Safety)
        intrinsic_value = None
        margin_of_safety_pct = None

        try:
            dcf_result = self.dcf_calculator.get_intrinsic_value(
                symbol, force_refresh=force_refresh
            )

            if dcf_result and dcf_result.intrinsic_value > 0:
                intrinsic_value = dcf_result.intrinsic_value
                margin_of_safety_pct = (intrinsic_value - market_price) / intrinsic_value

                logger.info(
                    f"{symbol} intrinsic value: ${intrinsic_value:.2f}, "
                    f"margin of safety: {margin_of_safety_pct * 100:.1f}%"
                )

                # Check margin of safety threshold
                if margin_of_safety_pct >= self.IDEAL_MARGIN_OF_SAFETY:
                    reasons.append(
                        f"Excellent margin of safety: {margin_of_safety_pct * 100:.1f}% "
                        f"(ideal: {self.IDEAL_MARGIN_OF_SAFETY * 100:.1f}%)"
                    )
                elif margin_of_safety_pct >= self.min_margin_of_safety:
                    reasons.append(
                        f"Adequate margin of safety: {margin_of_safety_pct * 100:.1f}% "
                        f"(minimum: {self.min_margin_of_safety * 100:.1f}%)"
                    )
                elif margin_of_safety_pct > 0:
                    warnings.append(
                        f"Low margin of safety: {margin_of_safety_pct * 100:.1f}% "
                        f"(below minimum: {self.min_margin_of_safety * 100:.1f}%)"
                    )
                else:
                    reasons.append(
                        f"No margin of safety - trading at premium: "
                        f"{abs(margin_of_safety_pct) * 100:.1f}% above intrinsic value"
                    )
            else:
                warnings.append("Unable to calculate intrinsic value - DCF analysis unavailable")
        except Exception as e:
            logger.warning(f"Error calculating intrinsic value for {symbol}: {e}")
            warnings.append(f"DCF calculation failed: {str(e)}")

        # Step 3: Quality Screening (Buffett's criteria)
        quality = None
        if self.require_quality_screening:
            try:
                quality = self._analyze_company_quality(symbol)

                if quality:
                    if quality.quality_score >= 80:
                        reasons.append(
                            f"High quality company (score: {quality.quality_score:.1f}/100)"
                        )
                    elif quality.quality_score >= 60:
                        reasons.append(
                            f"Good quality company (score: {quality.quality_score:.1f}/100)"
                        )
                    elif quality.quality_score >= 40:
                        warnings.append(
                            f"Moderate quality (score: {quality.quality_score:.1f}/100) - "
                            f"proceed with caution"
                        )
                    else:
                        reasons.append(
                            f"Low quality company (score: {quality.quality_score:.1f}/100) - "
                            f"fails quality screening"
                        )
            except Exception as e:
                logger.warning(f"Error analyzing company quality for {symbol}: {e}")
                warnings.append(f"Quality analysis failed: {str(e)}")

        # Step 4: Defensive Investor Analysis (Intelligent Investor)
        defensive_score = None
        if quality:
            defensive_score = self._calculate_defensive_investor_score(
                symbol, market_price, quality
            )
            if defensive_score:
                if defensive_score >= 80:
                    reasons.append(f"Excellent defensive investor score: {defensive_score:.1f}/100")
                elif defensive_score >= 60:
                    reasons.append(f"Good defensive investor score: {defensive_score:.1f}/100")
                elif defensive_score < 40:
                    warnings.append(
                        f"Low defensive investor score: {defensive_score:.1f}/100 - "
                        f"fails Graham's defensive criteria"
                    )

        # Step 5: Mr. Market Sentiment (Intelligent Investor concept)
        mr_market_sentiment = self._assess_mr_market_sentiment(
            symbol, market_price, intrinsic_value, quality
        )
        if mr_market_sentiment == "fearful":
            reasons.append("Mr. Market is fearful - opportunity to buy at attractive prices")
        elif mr_market_sentiment == "greedy":
            warnings.append("Mr. Market is greedy - prices may be inflated, wait for pullback")

        # Step 6: Value Score (Intelligent Investor)
        value_score = self._calculate_value_score(margin_of_safety_pct, quality, defensive_score)

        # Step 7: Determine Safety Rating
        safety_rating = self._determine_safety_rating(
            margin_of_safety_pct, quality, reasons, warnings, defensive_score
        )

        # Step 8: Additional Warnings
        if margin_of_safety_pct is not None and margin_of_safety_pct < 0:
            warnings.append("⚠️  Trading at premium to intrinsic value - no margin of safety")

        if quality and quality.quality_score < 40:
            warnings.append("⚠️  Low quality company - fails fundamental screening criteria")

        if quality and quality.pe_ratio and quality.pe_ratio > self.MAX_PE_RATIO_STRICT:
            warnings.append(
                f"⚠️  P/E ratio ({quality.pe_ratio:.1f}) exceeds maximum ({self.MAX_PE_RATIO_STRICT:.1f})"
            )

        if quality and quality.pb_ratio and quality.pb_ratio > self.MAX_PB_RATIO_STRICT:
            warnings.append(
                f"⚠️  P/B ratio ({quality.pb_ratio:.2f}) exceeds maximum ({self.MAX_PB_RATIO_STRICT:.2f})"
            )

        analysis = SafetyAnalysis(
            symbol=symbol,
            market_price=market_price,
            intrinsic_value=intrinsic_value,
            margin_of_safety_pct=margin_of_safety_pct,
            quality=quality,
            safety_rating=safety_rating,
            reasons=reasons,
            warnings=warnings,
            defensive_investor_score=defensive_score,
            mr_market_sentiment=mr_market_sentiment,
            value_score=value_score,
            timestamp=datetime.now(),
        )

        logger.info(
            f"{symbol} safety analysis complete: {safety_rating.value} "
            f"(margin: {margin_of_safety_pct * 100:.1f}% if available, "
            f"quality: {quality.quality_score if quality else 'N/A'})"
        )

        return analysis

    def should_buy(
        self,
        symbol: str,
        market_price: float,
        force_refresh: bool = False,
    ) -> tuple[bool, SafetyAnalysis]:
        """
        Determine if a stock should be purchased based on Graham-Buffett principles.

        Args:
            symbol: Stock ticker symbol
            market_price: Current market price
            force_refresh: Force refresh of DCF calculation

        Returns:
            Tuple of (should_buy: bool, analysis: SafetyAnalysis)
        """
        analysis = self.analyze_safety(symbol, market_price, force_refresh)

        # Require at least ACCEPTABLE rating to buy
        should_buy = analysis.safety_rating in [
            SafetyRating.EXCELLENT,
            SafetyRating.GOOD,
            SafetyRating.ACCEPTABLE,
        ]

        if not should_buy:
            logger.warning(f"❌ {symbol} REJECTED - Safety rating: {analysis.safety_rating.value}")
            for reason in analysis.reasons:
                logger.warning(f"  Reason: {reason}")
        else:
            logger.info(f"✅ {symbol} APPROVED - Safety rating: {analysis.safety_rating.value}")

        return should_buy, analysis

    def _is_in_circle_of_competence(self, symbol: str) -> bool:
        """
        Check if symbol is in circle of competence (well-known, understandable).

        Args:
            symbol: Stock ticker symbol

        Returns:
            True if in circle of competence, False otherwise
        """
        # ETFs are always acceptable (diversified, well-understood)
        if symbol in ["SPY", "QQQ", "VOO", "VTI", "DIA", "IWM"]:
            return True

        # Check well-known list
        if symbol in self.WELL_KNOWN_TICKERS:
            return True

        # For other symbols, check market cap (large-cap = more established)
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            market_cap = info.get("marketCap", 0)
            if market_cap >= self.MIN_MARKET_CAP:
                logger.info(f"{symbol} in circle of competence (market cap: ${market_cap:,.0f})")
                return True
            else:
                logger.warning(
                    f"{symbol} not in circle of competence "
                    f"(market cap: ${market_cap:,.0f} < ${self.MIN_MARKET_CAP:,.0f})"
                )
                return False
        except Exception as e:
            logger.warning(f"Error checking circle of competence for {symbol}: {e}")
            # Fail-open: allow if we can't verify
            return True

    def _analyze_company_quality(self, symbol: str) -> Optional[CompanyQuality]:
        """
        Analyze company quality using Buffett's criteria.

        Args:
            symbol: Stock ticker symbol

        Returns:
            CompanyQuality object or None if analysis fails
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            # Financial ratios
            debt_to_equity = info.get("debtToEquity")
            current_ratio = info.get("currentRatio")
            roe = info.get("returnOnEquity")
            roa = info.get("returnOnAssets")
            profit_margin = info.get("profitMargins")

            # Intelligent Investor metrics
            pe_ratio = info.get("trailingPE") or info.get("forwardPE")
            pb_ratio = info.get("priceToBook")
            dividend_yield = info.get("dividendYield")
            market_cap = info.get("marketCap")

            # Earnings data
            financials = ticker.financials
            financials = ticker.financials

            # Calculate 3-year earnings growth
            earnings_growth_3y = None
            earnings_consistency = 0.5  # Default moderate consistency

            if financials is not None and not financials.empty:
                try:
                    # Get net income for last 3 years
                    net_income = (
                        financials.loc["Net Income"] if "Net Income" in financials.index else None
                    )
                    if net_income is not None and len(net_income) >= 2:
                        # Calculate growth
                        years = (
                            net_income.index[:3] if len(net_income) >= 3 else net_income.index[:2]
                        )
                        if len(years) >= 2:
                            latest = net_income.iloc[0]
                            oldest = net_income.iloc[-1]
                            if oldest != 0:
                                earnings_growth_3y = (latest / oldest) ** (1 / (len(years) - 1)) - 1

                            # Calculate consistency (lower variance = higher consistency)
                            if len(net_income) >= 3:
                                values = net_income.iloc[:3].values
                                if all(v > 0 for v in values):
                                    # Positive earnings = good consistency
                                    earnings_consistency = 0.8
                                elif any(v > 0 for v in values):
                                    earnings_consistency = 0.5
                                else:
                                    earnings_consistency = 0.2
                except Exception as e:
                    logger.debug(f"Error calculating earnings metrics: {e}")

            # Calculate quality score (0-100)
            quality_score = self._calculate_quality_score(
                debt_to_equity=debt_to_equity,
                current_ratio=current_ratio,
                roe=roe,
                roa=roa,
                profit_margin=profit_margin,
                earnings_growth_3y=earnings_growth_3y,
                earnings_consistency=earnings_consistency,
            )

            return CompanyQuality(
                symbol=symbol,
                debt_to_equity=debt_to_equity,
                current_ratio=current_ratio,
                roe=roe,
                roa=roa,
                profit_margin=profit_margin,
                earnings_growth_3y=earnings_growth_3y,
                earnings_consistency=earnings_consistency,
                quality_score=quality_score,
                pe_ratio=pe_ratio,
                pb_ratio=pb_ratio,
                dividend_yield=dividend_yield,
                market_cap=market_cap,
                timestamp=datetime.now(),
            )
        except Exception as e:
            logger.error(f"Error analyzing company quality for {symbol}: {e}")
            return None

    def _calculate_quality_score(
        self,
        debt_to_equity: Optional[float],
        current_ratio: Optional[float],
        roe: Optional[float],
        roa: Optional[float],
        profit_margin: Optional[float],
        earnings_growth_3y: Optional[float],
        earnings_consistency: float,
    ) -> float:
        """
        Calculate composite quality score (0-100).

        Args:
            debt_to_equity: Debt to equity ratio
            current_ratio: Current ratio (liquidity)
            roe: Return on equity
            roa: Return on assets
            profit_margin: Net profit margin
            earnings_growth_3y: 3-year earnings growth
            earnings_consistency: Earnings consistency score (0-1)

        Returns:
            Quality score (0-100)
        """
        score = 0.0
        max_score = 0.0

        # Debt to Equity (20 points) - Lower is better
        if debt_to_equity is not None:
            max_score += 20
            if debt_to_equity <= 0.30:
                score += 20  # Excellent
            elif debt_to_equity <= 0.50:
                score += 15  # Good
            elif debt_to_equity <= 0.70:
                score += 10  # Acceptable
            elif debt_to_equity <= 1.0:
                score += 5  # Poor
            # >1.0 = 0 points

        # Current Ratio (15 points) - Higher is better
        if current_ratio is not None:
            max_score += 15
            if current_ratio >= 2.0:
                score += 15  # Excellent
            elif current_ratio >= 1.5:
                score += 12  # Good
            elif current_ratio >= 1.0:
                score += 8  # Acceptable
            elif current_ratio >= 0.5:
                score += 4  # Poor
            # <0.5 = 0 points

        # Return on Equity (20 points) - Higher is better
        if roe is not None:
            max_score += 20
            if roe >= 0.20:
                score += 20  # Excellent (>20%)
            elif roe >= 0.15:
                score += 16  # Good (15-20%)
            elif roe >= 0.10:
                score += 12  # Acceptable (10-15%)
            elif roe >= 0.05:
                score += 6  # Poor (5-10%)
            # <5% = 0 points

        # Return on Assets (15 points) - Higher is better
        if roa is not None:
            max_score += 15
            if roa >= 0.10:
                score += 15  # Excellent (>10%)
            elif roa >= 0.07:
                score += 12  # Good (7-10%)
            elif roa >= 0.05:
                score += 9  # Acceptable (5-7%)
            elif roa >= 0.02:
                score += 4  # Poor (2-5%)
            # <2% = 0 points

        # Profit Margin (15 points) - Higher is better
        if profit_margin is not None:
            max_score += 15
            if profit_margin >= 0.20:
                score += 15  # Excellent (>20%)
            elif profit_margin >= 0.15:
                score += 12  # Good (15-20%)
            elif profit_margin >= 0.10:
                score += 9  # Acceptable (10-15%)
            elif profit_margin >= 0.05:
                score += 4  # Poor (5-10%)
            # <5% = 0 points

        # Earnings Growth (10 points) - Higher is better
        if earnings_growth_3y is not None:
            max_score += 10
            if earnings_growth_3y >= 0.15:
                score += 10  # Excellent (>15%)
            elif earnings_growth_3y >= 0.10:
                score += 8  # Good (10-15%)
            elif earnings_growth_3y >= 0.05:
                score += 5  # Acceptable (5-10%)
            elif earnings_growth_3y >= 0:
                score += 2  # Poor (0-5%)
            # Negative = 0 points

        # Earnings Consistency (5 points) - Higher is better
        max_score += 5
        score += earnings_consistency * 5

        # Normalize to 0-100 scale
        if max_score > 0:
            normalized_score = (score / max_score) * 100
        else:
            normalized_score = 50.0  # Default if no data

        return round(normalized_score, 1)

    def _calculate_defensive_investor_score(
        self,
        symbol: str,
        market_price: float,
        quality: CompanyQuality,
    ) -> Optional[float]:
        """
        Calculate defensive investor score based on Graham's criteria from The Intelligent Investor.

        Defensive Investor Checklist (Graham):
        1. P/E ratio < 15 (preferred) or < 20 (maximum)
        2. P/B ratio < 1.5 (preferred) or < 2.0 (maximum)
        3. Dividend yield > 2% (preferred)
        4. Low debt-to-equity (< 50%)
        5. Consistent earnings growth
        6. Adequate liquidity (current ratio > 1.0)

        Args:
            symbol: Stock symbol
            market_price: Current market price
            quality: Company quality metrics

        Returns:
            Defensive investor score (0-100) or None if insufficient data
        """
        score = 0.0
        max_score = 0.0

        # P/E Ratio (30 points) - Lower is better for defensive investor
        if quality.pe_ratio is not None:
            max_score += 30
            if quality.pe_ratio <= self.MAX_PE_RATIO:
                score += 30  # Excellent (≤15)
            elif quality.pe_ratio <= 18:
                score += 20  # Good (15-18)
            elif quality.pe_ratio <= self.MAX_PE_RATIO_STRICT:
                score += 10  # Acceptable (18-20)
            else:
                score += 0  # Poor (>20)

        # P/B Ratio (25 points) - Lower is better for defensive investor
        if quality.pb_ratio is not None:
            max_score += 25
            if quality.pb_ratio <= self.MAX_PB_RATIO:
                score += 25  # Excellent (≤1.5)
            elif quality.pb_ratio <= 1.75:
                score += 15  # Good (1.5-1.75)
            elif quality.pb_ratio <= self.MAX_PB_RATIO_STRICT:
                score += 8  # Acceptable (1.75-2.0)
            else:
                score += 0  # Poor (>2.0)

        # Dividend Yield (20 points) - Higher is better for defensive investor
        if quality.dividend_yield is not None:
            max_score += 20
            if quality.dividend_yield >= 0.04:
                score += 20  # Excellent (≥4%)
            elif quality.dividend_yield >= self.MIN_DIVIDEND_YIELD:
                score += 15  # Good (≥2%)
            elif quality.dividend_yield >= 0.01:
                score += 8  # Acceptable (1-2%)
            else:
                score += 0  # Poor (<1%)
        else:
            # No dividend - penalize slightly for defensive investor
            max_score += 20
            score += 5  # Some companies don't pay dividends (growth stocks)

        # Debt-to-Equity (15 points) - Lower is better
        if quality.debt_to_equity is not None:
            max_score += 15
            if quality.debt_to_equity <= 0.30:
                score += 15  # Excellent (≤30%)
            elif quality.debt_to_equity <= self.MAX_DEBT_TO_EQUITY:
                score += 10  # Good (30-50%)
            elif quality.debt_to_equity <= 0.70:
                score += 5  # Acceptable (50-70%)
            else:
                score += 0  # Poor (>70%)

        # Current Ratio (10 points) - Higher is better (liquidity)
        if quality.current_ratio is not None:
            max_score += 10
            if quality.current_ratio >= 2.0:
                score += 10  # Excellent (≥2.0)
            elif quality.current_ratio >= self.MIN_CURRENT_RATIO:
                score += 7  # Good (≥1.0)
            elif quality.current_ratio >= 0.5:
                score += 3  # Acceptable (0.5-1.0)
            else:
                score += 0  # Poor (<0.5)

        # Normalize to 0-100 scale
        if max_score > 0:
            normalized_score = (score / max_score) * 100
        else:
            return None  # Insufficient data

        return round(normalized_score, 1)

    def _assess_mr_market_sentiment(
        self,
        symbol: str,
        market_price: float,
        intrinsic_value: Optional[float],
        quality: Optional[CompanyQuality],
    ) -> Optional[str]:
        """
        Assess Mr. Market sentiment (Graham's concept from The Intelligent Investor).

        Mr. Market is a metaphor for the stock market - sometimes fearful (prices low),
        sometimes greedy (prices high). We should be greedy when others are fearful,
        and fearful when others are greedy.

        Args:
            symbol: Stock symbol
            market_price: Current market price
            intrinsic_value: Calculated intrinsic value
            quality: Company quality metrics

        Returns:
            "fearful", "greedy", or "neutral"
        """
        # If we have intrinsic value, compare to market price
        if intrinsic_value and intrinsic_value > 0:
            discount_pct = (intrinsic_value - market_price) / intrinsic_value

            if discount_pct >= 0.30:
                return "fearful"  # Market is fearful - great buying opportunity
            elif discount_pct >= 0.15:
                return "fearful"  # Market is somewhat fearful - good opportunity
            elif discount_pct <= -0.20:
                return "greedy"  # Market is greedy - prices inflated
            elif discount_pct <= -0.10:
                return "greedy"  # Market is somewhat greedy - be cautious

        # Use P/E ratio as proxy if no intrinsic value
        if quality and quality.pe_ratio:
            if quality.pe_ratio <= self.MAX_PE_RATIO:
                return "fearful"  # Low P/E suggests market is fearful
            elif quality.pe_ratio >= 25:
                return "greedy"  # High P/E suggests market is greedy

        return "neutral"

    def _calculate_value_score(
        self,
        margin_of_safety_pct: Optional[float],
        quality: Optional[CompanyQuality],
        defensive_score: Optional[float],
    ) -> Optional[float]:
        """
        Calculate overall value investing score (0-100).

        Combines margin of safety, quality, and defensive investor criteria.

        Args:
            margin_of_safety_pct: Margin of safety percentage
            quality: Company quality metrics
            defensive_score: Defensive investor score

        Returns:
            Value score (0-100) or None if insufficient data
        """
        if not quality:
            return None

        score = 0.0
        max_score = 0.0

        # Margin of Safety (40 points)
        if margin_of_safety_pct is not None:
            max_score += 40
            if margin_of_safety_pct >= self.IDEAL_MARGIN_OF_SAFETY:
                score += 40  # Excellent (≥30%)
            elif margin_of_safety_pct >= self.min_margin_of_safety:
                score += 30  # Good (≥20%)
            elif margin_of_safety_pct > 0:
                score += 15  # Acceptable (>0%)
            else:
                score += 0  # Poor (no margin of safety)
        else:
            max_score += 40
            # If no intrinsic value, use P/E and P/B as proxies
            if quality.pe_ratio and quality.pe_ratio <= self.MAX_PE_RATIO:
                score += 25  # Good P/E suggests value
            elif quality.pe_ratio and quality.pe_ratio <= self.MAX_PE_RATIO_STRICT:
                score += 15  # Acceptable P/E

        # Quality Score (30 points)
        max_score += 30
        if quality.quality_score >= 80:
            score += 30  # Excellent
        elif quality.quality_score >= 60:
            score += 20  # Good
        elif quality.quality_score >= 40:
            score += 10  # Acceptable
        else:
            score += 0  # Poor

        # Defensive Investor Score (30 points)
        if defensive_score is not None:
            max_score += 30
            if defensive_score >= 80:
                score += 30  # Excellent
            elif defensive_score >= 60:
                score += 20  # Good
            elif defensive_score >= 40:
                score += 10  # Acceptable
            else:
                score += 0  # Poor

        # Normalize to 0-100 scale
        if max_score > 0:
            normalized_score = (score / max_score) * 100
        else:
            return None

        return round(normalized_score, 1)

    def _determine_safety_rating(
        self,
        margin_of_safety_pct: Optional[float],
        quality: Optional[CompanyQuality],
        reasons: list[str],
        warnings: list[str],
        defensive_score: Optional[float] = None,
    ) -> SafetyRating:
        """
        Determine overall safety rating based on all factors.

        Args:
            margin_of_safety_pct: Margin of safety percentage
            quality: Company quality metrics
            reasons: List of positive reasons
            warnings: List of warnings

        Returns:
            SafetyRating enum value
        """
        # Reject: P/E or P/B ratios exceed strict limits (Intelligent Investor)
        if quality:
            if quality.pe_ratio and quality.pe_ratio > self.MAX_PE_RATIO_STRICT:
                return SafetyRating.REJECT
            if quality.pb_ratio and quality.pb_ratio > self.MAX_PB_RATIO_STRICT:
                return SafetyRating.REJECT

        # Excellent: High margin of safety + high quality + good defensive score
        if (
            margin_of_safety_pct is not None
            and margin_of_safety_pct >= self.IDEAL_MARGIN_OF_SAFETY
            and quality
            and quality.quality_score >= 70
            and (defensive_score is None or defensive_score >= 70)
        ):
            return SafetyRating.EXCELLENT

        # Good: Adequate margin of safety + good quality + acceptable defensive score
        if (
            margin_of_safety_pct is not None
            and margin_of_safety_pct >= self.min_margin_of_safety
            and quality
            and quality.quality_score >= 60
            and (defensive_score is None or defensive_score >= 50)
        ):
            return SafetyRating.GOOD

        # Acceptable: Either good margin OR good quality OR good defensive score
        if (
            (margin_of_safety_pct is not None and margin_of_safety_pct >= self.min_margin_of_safety)
            or (quality and quality.quality_score >= 60)
            or (defensive_score is not None and defensive_score >= 60)
        ):
            return SafetyRating.ACCEPTABLE

        # Poor: Low margin of safety AND low quality AND low defensive score
        if (
            (margin_of_safety_pct is not None and margin_of_safety_pct < self.min_margin_of_safety)
            or (quality and quality.quality_score < 40)
            or (defensive_score is not None and defensive_score < 40)
        ):
            return SafetyRating.POOR

        # Reject: No margin of safety (trading at premium) OR very low quality OR very low defensive score
        if (
            (margin_of_safety_pct is not None and margin_of_safety_pct < 0)
            or (quality and quality.quality_score < 30)
            or (defensive_score is not None and defensive_score < 30)
        ):
            return SafetyRating.REJECT

        # Default: Reject if we can't determine
        return SafetyRating.REJECT


# Convenience singleton
_GLOBAL_SAFETY_ANALYZER: Optional[GrahamBuffettSafety] = None


def get_global_safety_analyzer() -> GrahamBuffettSafety:
    """Get or create global Graham-Buffett safety analyzer."""
    global _GLOBAL_SAFETY_ANALYZER
    if _GLOBAL_SAFETY_ANALYZER is None:
        _GLOBAL_SAFETY_ANALYZER = GrahamBuffettSafety()
    return _GLOBAL_SAFETY_ANALYZER
