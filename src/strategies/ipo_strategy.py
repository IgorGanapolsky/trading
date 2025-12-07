"""
IPO Analysis Strategy Module

Tier 3 (10% allocation): Manual IPO investing with AI decision support.

This module provides comprehensive analysis tools for IPO opportunities since SoFi
has no API access - all investments must be made manually through the platform.

The strategy uses multi-LLM analysis to evaluate IPO opportunities across multiple
dimensions including underwriter quality, financial health, market conditions, and
comparable company analysis.

Author: Trading System
Date: 2025-10-28
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import anthropic

from src.utils.langsmith_wrapper import get_traced_openai_client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class CompanyData:
    """
    Data structure for IPO company information.

    Attributes:
        name: Company name
        ticker: Proposed stock ticker symbol
        industry: Industry sector
        ipo_date: Expected IPO date
        price_range: Tuple of (low, high) price range
        shares_offered: Number of shares in the offering
        valuation: Company valuation estimate
        underwriters: List of underwriting banks
        revenue: Recent annual revenue
        revenue_growth: Year-over-year revenue growth percentage
        net_income: Recent net income (negative if loss)
        employees: Number of employees
        founded: Year company was founded
        ceo: CEO name
        business_model: Description of business model
        competitors: List of competitor companies
        risk_factors: List of key risk factors
        use_of_proceeds: How IPO funds will be used
        financials: Dictionary of additional financial metrics
    """

    name: str
    ticker: str
    industry: str
    ipo_date: str | None = None
    price_range: tuple[float, float] | None = None
    shares_offered: int | None = None
    valuation: float | None = None
    underwriters: list[str] = field(default_factory=list)
    revenue: float | None = None
    revenue_growth: float | None = None
    net_income: float | None = None
    employees: int | None = None
    founded: int | None = None
    ceo: str | None = None
    business_model: str | None = None
    competitors: list[str] = field(default_factory=list)
    risk_factors: list[str] = field(default_factory=list)
    use_of_proceeds: str | None = None
    financials: dict[str, Any] = field(default_factory=dict)


@dataclass
class IPOAnalysis:
    """
    Results of IPO analysis.

    Attributes:
        company_name: Name of the company analyzed
        ticker: Stock ticker symbol
        score: Overall score from 0-100
        recommendation: 'INVEST' or 'PASS'
        confidence: Confidence level ('HIGH', 'MEDIUM', 'LOW')
        strengths: List of positive factors
        risks: List of risk factors
        underwriter_rating: Quality rating of underwriters (0-10)
        financial_health: Financial health rating (0-10)
        market_timing: Market timing rating (0-10)
        comparable_analysis: Analysis vs comparable companies
        investment_thesis: Summary investment thesis
        red_flags: Critical concerns
        target_allocation: Recommended investment amount
        timestamp: Analysis timestamp
    """

    company_name: str
    ticker: str
    score: float
    recommendation: str
    confidence: str
    strengths: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    underwriter_rating: float = 0.0
    financial_health: float = 0.0
    market_timing: float = 0.0
    comparable_analysis: str = ""
    investment_thesis: str = ""
    red_flags: list[str] = field(default_factory=list)
    target_allocation: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class IPOStrategy:
    """
    IPO Analysis Strategy for manual investing with AI decision support.

    This class provides comprehensive tools for analyzing IPO opportunities using
    multi-LLM analysis. Since SoFi has no API, this focuses on decision support
    and analysis rather than automated trading.

    Features:
    - Daily deposit tracking ($1/day allocation)
    - Multi-LLM IPO analysis (Claude + GPT-4)
    - Comprehensive scoring system (0-100)
    - Detailed reports with pros/cons
    - Risk assessment and red flag detection
    - Comparable company analysis

    Attributes:
        balance: Current available balance for IPO investments
        daily_deposit: Daily deposit amount (default $1.00)
        analysis_history: List of past analyses
        data_dir: Directory for storing analysis data
    """

    def __init__(
        self,
        data_dir: str | None = None,
        daily_deposit: float = 1.0,
        anthropic_api_key: str | None = None,
        openai_api_key: str | None = None,
    ):
        """
        Initialize the IPO Strategy.

        Args:
            data_dir: Directory for storing IPO analysis data (defaults to project_root/data/ipo)
            daily_deposit: Daily deposit amount in dollars (default $1.00)
            anthropic_api_key: Anthropic API key for Claude analysis
            openai_api_key: OpenAI API key for GPT-4 analysis
        """
        # Use project root if data_dir not specified
        if data_dir is None:
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / "data" / "ipo"

        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.daily_deposit = daily_deposit
        self.balance_file = self.data_dir / "balance.json"
        self.history_file = self.data_dir / "analysis_history.json"

        # Initialize balance tracking
        self.balance = self._load_balance()
        self.analysis_history: list[dict[str, Any]] = self._load_history()

        # Initialize AI clients
        self.anthropic_client = None
        self.openai_client = None

        # Anthropic (Claude) with fallback to CLAUDE_API_KEY
        if not anthropic_api_key:
            from src.utils.self_healing import get_anthropic_api_key

            anthropic_api_key = get_anthropic_api_key()
        if anthropic_api_key:
            try:
                self.anthropic_client = anthropic.Anthropic(api_key=anthropic_api_key)
                logger.info("Anthropic client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Anthropic client: {e}")

        # OpenAI-compatible client via wrapper; defaults to OpenRouter if OpenAI key missing
        try:
            # If explicit key passed, use it; else wrapper falls back to OPENAI/OPENROUTER env
            self.openai_client = (
                get_traced_openai_client(api_key=openai_api_key)
                if openai_api_key
                else get_traced_openai_client()
            )
            logger.info("OpenAI-compatible client initialized (OpenAI/OpenRouter)")
        except Exception as e:
            logger.warning(f"Failed to initialize OpenAI-compatible client: {e}")

        logger.info(f"IPO Strategy initialized with balance: ${self.balance:.2f}")

    def _load_balance(self) -> float:
        """Load current balance from file."""
        if self.balance_file.exists():
            try:
                with open(self.balance_file) as f:
                    data = json.load(f)
                    return data.get("balance", 0.0)
            except Exception as e:
                logger.error(f"Error loading balance: {e}")
                return 0.0
        return 0.0

    def _save_balance(self) -> None:
        """Save current balance to file."""
        try:
            data = {
                "balance": self.balance,
                "last_updated": datetime.now().isoformat(),
                "daily_deposit": self.daily_deposit,
            }
            with open(self.balance_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving balance: {e}")

    def _load_history(self) -> list[dict[str, Any]]:
        """Load analysis history from file."""
        if self.history_file.exists():
            try:
                with open(self.history_file) as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading history: {e}")
                return []
        return []

    def _save_history(self) -> None:
        """Save analysis history to file."""
        try:
            with open(self.history_file, "w") as f:
                json.dump(self.analysis_history, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving history: {e}")

    def track_daily_deposit(self, amount: float | None = None) -> float:
        """
        Track daily deposit to IPO allocation.

        This method should be called daily to add the daily deposit amount
        to the available balance for IPO investments.

        Args:
            amount: Deposit amount (defaults to daily_deposit if not specified)

        Returns:
            Current balance after deposit

        Example:
            >>> strategy = IPOStrategy()
            >>> balance = strategy.track_daily_deposit()
            >>> print(f"New balance: ${balance:.2f}")
        """
        if amount is None:
            amount = self.daily_deposit

        self.balance += amount
        self._save_balance()

        logger.info(f"Deposited ${amount:.2f}. New balance: ${self.balance:.2f}")
        return self.balance

    def _evaluate_underwriters(self, underwriters: list[str]) -> tuple[float, str]:
        """
        Evaluate quality of IPO underwriters.

        Top-tier underwriters (Goldman Sachs, Morgan Stanley, JPMorgan, etc.)
        are associated with better IPO performance.

        Args:
            underwriters: List of underwriting banks

        Returns:
            Tuple of (rating 0-10, analysis text)
        """
        top_tier = {
            "goldman sachs",
            "morgan stanley",
            "jpmorgan",
            "jp morgan",
            "bank of america",
            "bofa",
            "citigroup",
            "citi",
            "deutsche bank",
            "credit suisse",
            "barclays",
            "ubs",
        }

        mid_tier = {
            "wells fargo",
            "rbc",
            "jefferies",
            "cowen",
            "piper sandler",
            "william blair",
            "stifel",
            "raymond james",
            "canaccord",
        }

        underwriter_lower = [u.lower() for u in underwriters]

        top_tier_count = sum(1 for u in underwriter_lower if any(t in u for t in top_tier))
        mid_tier_count = sum(1 for u in underwriter_lower if any(m in u for m in mid_tier))

        if top_tier_count >= 2:
            rating = 9.0
            analysis = f"Excellent underwriter syndicate with {top_tier_count} top-tier banks"
        elif top_tier_count == 1:
            rating = 7.5
            analysis = "Strong lead underwriter from top tier"
        elif mid_tier_count >= 2:
            rating = 6.0
            analysis = "Solid mid-tier underwriting team"
        elif mid_tier_count == 1:
            rating = 5.0
            analysis = "Moderate underwriting quality"
        else:
            rating = 3.0
            analysis = "Weaker underwriting syndicate - higher risk"

        return rating, analysis

    def _evaluate_financials(self, company: CompanyData) -> tuple[float, list[str], list[str]]:
        """
        Evaluate company financial health.

        Args:
            company: Company data

        Returns:
            Tuple of (rating 0-10, strengths list, concerns list)
        """
        rating = 5.0  # Start neutral
        strengths = []
        concerns = []

        # Revenue growth
        if company.revenue_growth is not None:
            if company.revenue_growth > 50:
                rating += 2.0
                strengths.append(f"Exceptional revenue growth: {company.revenue_growth:.1f}%")
            elif company.revenue_growth > 25:
                rating += 1.5
                strengths.append(f"Strong revenue growth: {company.revenue_growth:.1f}%")
            elif company.revenue_growth > 10:
                rating += 0.5
                strengths.append(f"Solid revenue growth: {company.revenue_growth:.1f}%")
            elif company.revenue_growth < 0:
                rating -= 2.0
                concerns.append(f"Declining revenue: {company.revenue_growth:.1f}%")

        # Profitability
        if company.net_income is not None and company.revenue is not None:
            margin = (company.net_income / company.revenue) * 100 if company.revenue > 0 else -100
            if margin > 20:
                rating += 1.5
                strengths.append(f"Highly profitable: {margin:.1f}% margin")
            elif margin > 10:
                rating += 1.0
                strengths.append(f"Profitable: {margin:.1f}% margin")
            elif margin > 0:
                rating += 0.5
                strengths.append(f"Positive margins: {margin:.1f}%")
            else:
                if company.revenue and company.revenue > 1_000_000_000:  # Over $1B revenue
                    concerns.append(
                        f"Not yet profitable: {margin:.1f}% margin (acceptable for growth stage)"
                    )
                else:
                    rating -= 1.0
                    concerns.append(f"Unprofitable: {margin:.1f}% margin")

        # Valuation reasonableness
        if company.valuation and company.revenue:
            ps_ratio = company.valuation / company.revenue
            if ps_ratio < 5:
                rating += 1.0
                strengths.append(f"Reasonable valuation: {ps_ratio:.1f}x revenue")
            elif ps_ratio > 20:
                rating -= 1.0
                concerns.append(f"High valuation: {ps_ratio:.1f}x revenue")

        # Cap rating at 0-10
        rating = max(0.0, min(10.0, rating))

        return rating, strengths, concerns

    def _evaluate_market_timing(self) -> tuple[float, str]:
        """
        Evaluate current market conditions for IPOs.

        Returns:
            Tuple of (rating 0-10, analysis text)
        """
        # This is a simplified heuristic - in production, you'd want to:
        # - Check market indices (S&P 500, Nasdaq)
        # - Analyze recent IPO performance
        # - Check volatility (VIX)
        # - Review Fed policy and interest rates

        # For now, return moderate rating with reminder to check manually
        rating = 6.0
        analysis = (
            "Market timing evaluation requires manual assessment. "
            "Check: (1) Recent market performance, (2) VIX level, "
            "(3) Recent IPO performance, (4) Interest rate environment"
        )

        return rating, analysis

    def _get_claude_analysis(self, company: CompanyData) -> str | None:
        """
        Get IPO analysis from Claude.

        Args:
            company: Company data

        Returns:
            Analysis text or None if unavailable
        """
        if not self.anthropic_client:
            return None

        try:
            prompt = f"""Analyze this IPO opportunity:

Company: {company.name} ({company.ticker})
Industry: {company.industry}
Valuation: ${company.valuation:,.0f if company.valuation else 0}
Revenue: ${company.revenue:,.0f if company.revenue else 0}
Revenue Growth: {company.revenue_growth if company.revenue_growth else "N/A"}%
Net Income: ${company.net_income:,.0f if company.net_income else 0}
Underwriters: {", ".join(company.underwriters)}

Business Model: {company.business_model or "N/A"}
Competitors: {", ".join(company.competitors) if company.competitors else "N/A"}

Provide a concise analysis covering:
1. Investment thesis (2-3 sentences)
2. Key strengths (3-5 points)
3. Major risks (3-5 points)
4. Comparison to competitors
5. Overall recommendation (INVEST or PASS) with confidence level

Be direct and analytical. Focus on facts over speculation."""

            message = self.anthropic_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )

            return message.content[0].text

        except Exception as e:
            logger.error(f"Error getting Claude analysis: {e}")
            return None

    def _get_gpt4_analysis(self, company: CompanyData) -> str | None:
        """
        Get IPO analysis from GPT-4.

        Args:
            company: Company data

        Returns:
            Analysis text or None if unavailable
        """
        if not self.openai_client:
            return None

        try:
            prompt = f"""Analyze this IPO opportunity:

Company: {company.name} ({company.ticker})
Industry: {company.industry}
Valuation: ${company.valuation:,.0f if company.valuation else 0}
Revenue: ${company.revenue:,.0f if company.revenue else 0}
Revenue Growth: {company.revenue_growth if company.revenue_growth else "N/A"}%
Net Income: ${company.net_income:,.0f if company.net_income else 0}
Underwriters: {", ".join(company.underwriters)}

Business Model: {company.business_model or "N/A"}
Competitors: {", ".join(company.competitors) if company.competitors else "N/A"}

Provide analysis covering:
1. Competitive positioning
2. Financial health assessment
3. Market opportunity
4. Key risks and concerns
5. Investment recommendation with reasoning

Be analytical and balanced."""

            response = self.openai_client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1500,
                temperature=0.7,
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Error getting GPT-4 analysis: {e}")
            return None

    def analyze_ipo(self, company_data: dict[str, Any]) -> dict[str, Any]:
        """
        Analyze an IPO opportunity using multi-LLM analysis.

        This method performs comprehensive analysis including:
        - Underwriter quality evaluation
        - Financial health assessment
        - Market timing analysis
        - Multi-LLM AI analysis (Claude + GPT-4)
        - Risk factor identification
        - Investment recommendation

        Args:
            company_data: Dictionary containing company information
                         (will be converted to CompanyData object)

        Returns:
            Dictionary containing analysis results with keys:
            - score: Overall score (0-100)
            - recommendation: 'INVEST' or 'PASS'
            - confidence: 'HIGH', 'MEDIUM', or 'LOW'
            - strengths: List of positive factors
            - risks: List of risk factors
            - red_flags: Critical concerns
            - investment_thesis: Summary thesis
            - detailed_analysis: Full analysis text
            - target_allocation: Recommended investment amount

        Example:
            >>> company = {
            ...     'name': 'TechCo',
            ...     'ticker': 'TECH',
            ...     'industry': 'Software',
            ...     'valuation': 5_000_000_000,
            ...     'revenue': 500_000_000,
            ...     'revenue_growth': 45.0,
            ...     'underwriters': ['Goldman Sachs', 'Morgan Stanley']
            ... }
            >>> analysis = strategy.analyze_ipo(company)
            >>> print(f"Score: {analysis['score']}, Recommendation: {analysis['recommendation']}")
        """
        # Convert dict to CompanyData object
        company = CompanyData(**company_data)

        logger.info(f"Analyzing IPO: {company.name} ({company.ticker})")

        # Initialize analysis components
        strengths = []
        risks = []
        red_flags = []

        # 1. Evaluate underwriters (20% of score)
        underwriter_rating, underwriter_analysis = self._evaluate_underwriters(company.underwriters)
        underwriter_score = (underwriter_rating / 10) * 20

        if underwriter_rating >= 7:
            strengths.append(underwriter_analysis)
        else:
            risks.append(underwriter_analysis)

        # 2. Evaluate financials (40% of score)
        financial_rating, fin_strengths, fin_concerns = self._evaluate_financials(company)
        financial_score = (financial_rating / 10) * 40
        strengths.extend(fin_strengths)
        risks.extend(fin_concerns)

        # 3. Evaluate market timing (15% of score)
        market_rating, market_analysis = self._evaluate_market_timing()
        market_score = (market_rating / 10) * 15

        # 4. Get AI analysis (25% of score, bonus points)
        ai_score = 0
        ai_analyses = []

        claude_analysis = self._get_claude_analysis(company)
        if claude_analysis:
            ai_analyses.append(("Claude Analysis", claude_analysis))
            ai_score += 12.5

        gpt4_analysis = self._get_gpt4_analysis(company)
        if gpt4_analysis:
            ai_analyses.append(("GPT-4 Analysis", gpt4_analysis))
            ai_score += 12.5

        # 5. Check for red flags
        if company.revenue_growth and company.revenue_growth < -10:
            red_flags.append("Significant revenue decline")

        if company.net_income and company.revenue and company.revenue > 1_000_000_000:
            margin = (company.net_income / company.revenue) * 100
            if margin < -50:
                red_flags.append("Severe losses relative to revenue")

        if underwriter_rating < 4:
            red_flags.append("Weak underwriting syndicate")

        if len(company.risk_factors) > 10:
            red_flags.append(f"Excessive risk factors disclosed: {len(company.risk_factors)}")

        # Calculate total score
        total_score = underwriter_score + financial_score + market_score + ai_score

        # Apply red flag penalty
        red_flag_penalty = len(red_flags) * 5
        total_score = max(0, total_score - red_flag_penalty)

        # Determine recommendation and confidence
        if total_score >= 75 and len(red_flags) == 0:
            recommendation = "INVEST"
            confidence = "HIGH"
        elif total_score >= 65 and len(red_flags) <= 1:
            recommendation = "INVEST"
            confidence = "MEDIUM"
        elif total_score >= 55 and len(red_flags) == 0:
            recommendation = "INVEST"
            confidence = "LOW"
        else:
            recommendation = "PASS"
            confidence = "HIGH" if total_score < 40 or len(red_flags) >= 2 else "MEDIUM"

        # Calculate target allocation
        if recommendation == "INVEST":
            # Allocate based on score and confidence
            if confidence == "HIGH":
                target_allocation = min(self.balance * 0.3, self.balance)
            elif confidence == "MEDIUM":
                target_allocation = min(self.balance * 0.2, self.balance)
            else:
                target_allocation = min(self.balance * 0.1, self.balance)
        else:
            target_allocation = 0.0

        # Build investment thesis
        thesis_parts = []
        if strengths:
            thesis_parts.append(f"Strengths: {', '.join(strengths[:2])}")
        if risks:
            thesis_parts.append(f"Key risks: {', '.join(risks[:2])}")

        investment_thesis = (
            ". ".join(thesis_parts) if thesis_parts else "Insufficient data for thesis"
        )

        # Create analysis object
        analysis = IPOAnalysis(
            company_name=company.name,
            ticker=company.ticker,
            score=round(total_score, 1),
            recommendation=recommendation,
            confidence=confidence,
            strengths=strengths,
            risks=risks,
            red_flags=red_flags,
            underwriter_rating=underwriter_rating,
            financial_health=financial_rating,
            market_timing=market_rating,
            investment_thesis=investment_thesis,
            target_allocation=round(target_allocation, 2),
            comparable_analysis=market_analysis,
        )

        # Add to history
        history_entry = asdict(analysis)
        history_entry["company_data"] = asdict(company)
        history_entry["ai_analyses"] = ai_analyses
        self.analysis_history.append(history_entry)
        self._save_history()

        logger.info(
            f"Analysis complete: {company.name} - "
            f"Score: {total_score:.1f}, "
            f"Recommendation: {recommendation} ({confidence})"
        )

        # Return as dictionary
        result = asdict(analysis)
        result["ai_analyses"] = ai_analyses
        result["detailed_breakdown"] = {
            "underwriter_score": round(underwriter_score, 1),
            "financial_score": round(financial_score, 1),
            "market_score": round(market_score, 1),
            "ai_score": round(ai_score, 1),
            "red_flag_penalty": red_flag_penalty,
        }

        return result

    def generate_ipo_report(
        self,
        company_name: str,
        analysis: dict[str, Any],
        output_file: str | None = None,
    ) -> None:
        """
        Generate detailed IPO analysis report.

        Creates a comprehensive markdown report with all analysis details,
        suitable for manual review before making investment decisions.

        Args:
            company_name: Name of the company
            analysis: Analysis results from analyze_ipo()
            output_file: Optional output file path (defaults to data_dir)

        Example:
            >>> analysis = strategy.analyze_ipo(company_data)
            >>> strategy.generate_ipo_report('TechCo', analysis)
            Report saved to: /path/to/TechCo_IPO_Analysis_2025-10-28.md
        """
        if output_file is None:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            safe_name = "".join(c for c in company_name if c.isalnum() or c in (" ", "-", "_"))
            output_file = str(self.data_dir / f"{safe_name}_IPO_Analysis_{timestamp}.md")

        # Build report
        report = f"""# IPO Analysis Report: {company_name}

**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Ticker:** {analysis["ticker"]}
**Overall Score:** {analysis["score"]}/100

---

## RECOMMENDATION: {analysis["recommendation"]}
**Confidence Level:** {analysis["confidence"]}

### Target Allocation
${analysis["target_allocation"]:.2f} (Available Balance: ${self.balance:.2f})

---

## Investment Thesis

{analysis["investment_thesis"]}

---

## Score Breakdown

| Component | Score | Rating |
|-----------|-------|--------|
| Underwriters | {analysis["detailed_breakdown"]["underwriter_score"]:.1f}/20 | {analysis["underwriter_rating"]:.1f}/10 |
| Financial Health | {analysis["detailed_breakdown"]["financial_score"]:.1f}/40 | {analysis["financial_health"]:.1f}/10 |
| Market Timing | {analysis["detailed_breakdown"]["market_score"]:.1f}/15 | {analysis["market_timing"]:.1f}/10 |
| AI Analysis | {analysis["detailed_breakdown"]["ai_score"]:.1f}/25 | - |
| **Total** | **{analysis["score"]:.1f}/100** | - |

Red Flag Penalty: -{analysis["detailed_breakdown"]["red_flag_penalty"]} points

---

## Strengths

"""

        for i, strength in enumerate(analysis["strengths"], 1):
            report += f"{i}. {strength}\n"

        if not analysis["strengths"]:
            report += "_No significant strengths identified_\n"

        report += "\n---\n\n## Risks\n\n"

        for i, risk in enumerate(analysis["risks"], 1):
            report += f"{i}. {risk}\n"

        if not analysis["risks"]:
            report += "_No significant risks identified_\n"

        if analysis["red_flags"]:
            report += "\n---\n\n## RED FLAGS\n\n"
            for i, flag in enumerate(analysis["red_flags"], 1):
                report += f"**{i}. {flag}**\n"

        # Add AI analyses
        if "ai_analyses" in analysis and analysis["ai_analyses"]:
            report += "\n---\n\n## AI Analyses\n\n"
            for model_name, ai_analysis in analysis["ai_analyses"]:
                report += f"### {model_name}\n\n{ai_analysis}\n\n"

        # Add comparable analysis
        report += f"\n---\n\n## Market & Comparables\n\n{analysis['comparable_analysis']}\n"

        # Add action items
        report += "\n---\n\n## Next Steps\n\n"
        if analysis["recommendation"] == "INVEST":
            report += f"""1. Review this analysis thoroughly
2. Check SoFi for IPO availability and terms
3. Review S-1 filing for additional details
4. Verify current market conditions
5. If approved, invest up to ${analysis["target_allocation"]:.2f}
6. Set calendar reminder for lock-up expiration (typically 180 days)
"""
        else:
            report += """1. Review analysis to understand concerns
2. Monitor company progress for potential future opportunities
3. Consider waiting for post-IPO price action
4. Focus available capital on higher-rated opportunities
"""

        # Add disclaimer
        report += """
---

## Disclaimer

This analysis is for informational purposes only and does not constitute financial advice.
IPO investing carries significant risks including potential loss of principal. Always conduct
your own due diligence and consider consulting with a financial advisor before making
investment decisions.

"""

        # Save report
        try:
            with open(output_file, "w") as f:
                f.write(report)
            logger.info(f"Report saved to: {output_file}")
            print(f"\nReport saved to: {output_file}")
        except Exception as e:
            logger.error(f"Error saving report: {e}")
            print(f"\nError saving report: {e}")
            print("\nReport content:")
            print(report)

    def check_sofi_offerings(self) -> None:
        """
        Print reminder to manually check SoFi for available IPO offerings.

        Since SoFi has no API, this method provides instructions for manually
        checking the platform for available IPO opportunities.

        Example:
            >>> strategy.check_sofi_offerings()
        """
        print("\n" + "=" * 70)
        print("MANUAL ACTION REQUIRED: Check SoFi IPO Offerings")
        print("=" * 70)
        print("\nSteps to check SoFi for IPO opportunities:")
        print("\n1. Log in to SoFi Invest platform")
        print("   https://www.sofi.com/invest/")
        print("\n2. Navigate to IPO section:")
        print("   - Click 'Trade' or 'Invest'")
        print("   - Look for 'IPOs' or 'Upcoming IPOs' section")
        print("\n3. Review available offerings:")
        print("   - Check company name, ticker, and industry")
        print("   - Note price range and expected IPO date")
        print("   - Review key financials and business description")
        print("\n4. For any interesting IPOs, gather data:")
        print("   - Company name and ticker")
        print("   - Underwriters")
        print("   - Financial metrics (revenue, growth, profitability)")
        print("   - Valuation and shares offered")
        print("\n5. Use this data with analyze_ipo() method for AI analysis")
        print("\n" + "=" * 70)
        print(f"Current IPO Balance: ${self.balance:.2f}")
        print("=" * 70 + "\n")

    def get_ipo_recommendations(self) -> list[dict[str, Any]]:
        """
        Get list of IPO recommendations from analysis history.

        Returns all analyses with INVEST recommendation, sorted by score.

        Returns:
            List of dictionaries containing recommendation details:
            - company_name: Company name
            - ticker: Stock ticker
            - score: Analysis score
            - recommendation: Always 'INVEST'
            - confidence: Confidence level
            - target_allocation: Recommended investment amount
            - timestamp: Analysis timestamp
            - investment_thesis: Summary thesis

        Example:
            >>> recommendations = strategy.get_ipo_recommendations()
            >>> for rec in recommendations:
            ...     print(f"{rec['company_name']}: {rec['score']}/100 - ${rec['target_allocation']}")
        """
        # Filter for INVEST recommendations
        recommendations = [
            entry for entry in self.analysis_history if entry.get("recommendation") == "INVEST"
        ]

        # Sort by score (highest first)
        recommendations.sort(key=lambda x: x.get("score", 0), reverse=True)

        # Return simplified list
        simplified = []
        for rec in recommendations:
            simplified.append(
                {
                    "company_name": rec["company_name"],
                    "ticker": rec["ticker"],
                    "score": rec["score"],
                    "recommendation": rec["recommendation"],
                    "confidence": rec["confidence"],
                    "target_allocation": rec["target_allocation"],
                    "timestamp": rec["timestamp"],
                    "investment_thesis": rec["investment_thesis"],
                }
            )

        return simplified

    def get_analysis_history(
        self, limit: int | None = None, recommendation_filter: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Get IPO analysis history.

        Args:
            limit: Maximum number of results to return
            recommendation_filter: Filter by recommendation ('INVEST' or 'PASS')

        Returns:
            List of analysis records

        Example:
            >>> # Get last 10 analyses
            >>> history = strategy.get_analysis_history(limit=10)
            >>> # Get all PASS recommendations
            >>> passes = strategy.get_analysis_history(recommendation_filter='PASS')
        """
        history = self.analysis_history.copy()

        # Apply filter
        if recommendation_filter:
            history = [h for h in history if h.get("recommendation") == recommendation_filter]

        # Apply limit
        if limit:
            history = history[-limit:]

        return history

    def get_balance_info(self) -> dict[str, Any]:
        """
        Get current balance and deposit information.

        Returns:
            Dictionary with balance, daily deposit, and projected balance

        Example:
            >>> info = strategy.get_balance_info()
            >>> print(f"Current: ${info['balance']:.2f}")
            >>> print(f"Projected 30 days: ${info['projected_30_days']:.2f}")
        """
        return {
            "balance": self.balance,
            "daily_deposit": self.daily_deposit,
            "projected_7_days": self.balance + (self.daily_deposit * 7),
            "projected_30_days": self.balance + (self.daily_deposit * 30),
            "projected_90_days": self.balance + (self.daily_deposit * 90),
        }


def main():
    """
    Example usage and testing of IPO Strategy.
    """
    print("IPO Strategy Module - Example Usage\n")

    # Initialize strategy
    strategy = IPOStrategy(daily_deposit=1.0)

    # Track some deposits
    print("1. Tracking daily deposits...")
    for _ in range(5):
        balance = strategy.track_daily_deposit()
    print(f"   Balance after 5 days: ${balance:.2f}\n")

    # Example company data
    example_company = {
        "name": "Example Tech Corp",
        "ticker": "EXTECH",
        "industry": "Cloud Software",
        "ipo_date": "2025-11-15",
        "price_range": (18.0, 22.0),
        "shares_offered": 10_000_000,
        "valuation": 2_500_000_000,
        "underwriters": ["Goldman Sachs", "Morgan Stanley", "JPMorgan"],
        "revenue": 300_000_000,
        "revenue_growth": 45.0,
        "net_income": -50_000_000,
        "employees": 1200,
        "founded": 2018,
        "ceo": "Jane Smith",
        "business_model": "SaaS platform for enterprise cloud infrastructure management",
        "competitors": ["Datadog", "New Relic", "Dynatrace"],
        "risk_factors": [
            "Competition from established players",
            "Dependence on cloud infrastructure providers",
            "Customer concentration risk",
        ],
    }

    # Analyze IPO
    print("2. Analyzing IPO...")
    analysis = strategy.analyze_ipo(example_company)

    print(f"\n   Company: {analysis['company_name']}")
    print(f"   Score: {analysis['score']}/100")
    print(f"   Recommendation: {analysis['recommendation']} ({analysis['confidence']} confidence)")
    print(f"   Target Allocation: ${analysis['target_allocation']:.2f}")

    # Generate report
    print("\n3. Generating detailed report...")
    strategy.generate_ipo_report(example_company["name"], analysis)

    # Check SoFi offerings reminder
    print("\n4. SoFi Manual Check:")
    strategy.check_sofi_offerings()

    # Get recommendations
    print("\n5. Current Recommendations:")
    recommendations = strategy.get_ipo_recommendations()
    if recommendations:
        for rec in recommendations:
            print(
                f"   - {rec['company_name']}: {rec['score']}/100 (${rec['target_allocation']:.2f})"
            )
    else:
        print("   No INVEST recommendations yet")

    # Balance info
    print("\n6. Balance Information:")
    balance_info = strategy.get_balance_info()
    print(f"   Current: ${balance_info['balance']:.2f}")
    print(f"   Projected (30 days): ${balance_info['projected_30_days']:.2f}")
    print(f"   Projected (90 days): ${balance_info['projected_90_days']:.2f}")


if __name__ == "__main__":
    main()
