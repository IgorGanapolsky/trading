"""PLAN Framework ETF Evaluator & $10K Scenario Simulator.

Inspired by Rico Nasol's P.L.A.N. Framework (Freedom Builder):
Pre-trade screening system to avoid yield traps and evaluate income ETFs:
  - P: Payout Sustainability (Is yield covered by realistic options premium / dividends?)
  - L: Liquidity & Fund Size (AUM > $100M, tight bid-ask, no toxic leverage)
  - A: Asset Quality (Underlying index/equities vs speculative single-stock synthetics)
  - N: NAV Trend (Capital preservation over 1-year/inception; stops slow principal liquidation)

Includes the '$10K Scenario': Standardized stress-test modeling $10,000 invested.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ETFProfile:
    symbol: str
    name: str
    headline_yield_pct: float  # e.g. 0.112 for 11.2%
    aum_millions_usd: float  # e.g. 1500.0 for $1.5B
    underlying_type: str  # "Broad Index", "Mega Tech", "Single Stock Synthetic", "Treasury"
    nav_1yr_change_pct: float  # e.g. 0.02 for +2%, -0.25 for -25%
    distribution_coverage_ratio: float  # e.g. 1.05 for fully covered, 0.60 for destructive ROC
    tax_treatment: str  # "Section 1256 60/40", "Qualified", "Ordinary"
    expense_ratio_pct: float  # e.g. 0.0068 for 0.68%


@dataclass(frozen=True)
class TenKScenarioResult:
    initial_investment_usd: float
    annual_gross_distribution_usd: float
    annual_net_distribution_usd: float
    monthly_net_distribution_usd: float
    projected_nav_ending_usd: float
    projected_total_return_usd: float
    projected_total_return_pct: float
    is_yield_trap: bool


@dataclass(frozen=True)
class PLANScore:
    symbol: str
    payout_score: float  # 0.0 to 10.0
    liquidity_score: float
    asset_score: float
    nav_score: float
    total_score: float  # 0.0 to 40.0
    passed: bool
    verdict: str  # "APPROVED_CORE", "APPROVED_SATELLITE", "REJECTED_YIELD_TRAP"
    findings: list[str] = field(default_factory=list)
    ten_k_scenario: TenKScenarioResult | None = None

    def summary(self) -> str:
        return (
            f"PLAN({self.symbol}): {self.verdict} (Score={self.total_score:.1f}/40) | "
            f"P={self.payout_score:.1f} L={self.liquidity_score:.1f} "
            f"A={self.asset_score:.1f} N={self.nav_score:.1f}"
        )


class PlanETFEvaluator:
    """Evaluates income instruments using the sequential P.L.A.N. criteria."""

    def evaluate(self, etf: ETFProfile) -> PLANScore:
        findings: list[str] = []

        # 1. P — Payout Sustainability (0-10)
        # Yields > 25% are almost always destructive synthetic traps
        if etf.headline_yield_pct > 0.25 or etf.distribution_coverage_ratio < 0.70:
            p_score = 2.0
            findings.append(
                "POOR_PAYOUT_SUSTAINABILITY: Extreme yield or severe destructive ROC coverage."
            )
        elif etf.distribution_coverage_ratio >= 0.95:
            p_score = 10.0
        else:
            p_score = 7.0

        # 2. L — Liquidity & AUM (0-10)
        if etf.aum_millions_usd < 50.0:
            l_score = 3.0
            findings.append("LOW_LIQUIDITY: Fund AUM below $50M threshold.")
        elif etf.aum_millions_usd >= 500.0:
            l_score = 10.0
        else:
            l_score = 7.5

        # 3. A — Asset Quality (0-10)
        if etf.underlying_type in ("Broad Index", "Treasury"):
            a_score = 10.0
        elif etf.underlying_type == "Mega Tech":
            a_score = 8.5
        elif etf.underlying_type == "Single Stock Synthetic":
            a_score = 2.0
            findings.append(
                "WEAK_ASSET_QUALITY: Single-stock synthetic exposure has uncapped downside."
            )
        else:
            a_score = 5.0

        # 4. N — NAV Trend (0-10)
        if etf.nav_1yr_change_pct < -0.15:
            n_score = 1.0
            findings.append(
                f"SEVERE_NAV_EROSION: 1-year NAV decline of {etf.nav_1yr_change_pct:.1%}."
            )
        elif etf.nav_1yr_change_pct >= 0.0:
            n_score = 10.0
        else:
            # Moderate decline (-5% to -15%)
            n_score = 6.0

        total_score = p_score + l_score + a_score + n_score

        # Yield trap detection: High headline yield combined with severe NAV decay
        is_yield_trap = (etf.headline_yield_pct >= 0.18 and etf.nav_1yr_change_pct <= -0.15) or (
            a_score <= 3.0 and n_score <= 3.0
        )

        # $10K Scenario calculation
        tax_rate = (
            0.18
            if "1256" in etf.tax_treatment
            else (0.15 if "Qualified" in etf.tax_treatment else 0.24)
        )
        ten_k_gross = 10000.0 * etf.headline_yield_pct
        ten_k_net = ten_k_gross * (1.0 - tax_rate)
        nav_ending = 10000.0 * (1.0 + etf.nav_1yr_change_pct)
        total_return_usd = (nav_ending + ten_k_net) - 10000.0
        total_return_pct = (total_return_usd / 10000.0) * 100.0

        ten_k = TenKScenarioResult(
            initial_investment_usd=10000.0,
            annual_gross_distribution_usd=round(ten_k_gross, 2),
            annual_net_distribution_usd=round(ten_k_net, 2),
            monthly_net_distribution_usd=round(ten_k_net / 12.0, 2),
            projected_nav_ending_usd=round(nav_ending, 2),
            projected_total_return_usd=round(total_return_usd, 2),
            projected_total_return_pct=round(total_return_pct, 2),
            is_yield_trap=is_yield_trap,
        )

        if is_yield_trap or total_score < 24.0:
            verdict = "REJECTED_YIELD_TRAP"
            passed = False
        elif total_score >= 34.0:
            verdict = "APPROVED_CORE"
            passed = True
        else:
            verdict = "APPROVED_SATELLITE"
            passed = True

        return PLANScore(
            symbol=etf.symbol,
            payout_score=p_score,
            liquidity_score=l_score,
            asset_score=a_score,
            nav_score=n_score,
            total_score=total_score,
            passed=passed,
            verdict=verdict,
            findings=findings,
            ten_k_scenario=ten_k,
        )
