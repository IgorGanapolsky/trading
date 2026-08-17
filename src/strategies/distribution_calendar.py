"""Distribution Calendar & Windfall Reinvestment Engine.

Inspired by Snowball Analytics (payout calendar / forward yield) and
Windfall Capital Allocation policies:
1. Projects exact 12-month forward distribution schedules for the 3-Bucket system
   (Monthly: SPYI, QQQI, JEPQ, DIVO, SGOV; Quarterly: SCHD, DGRO).
2. Computes Yield-on-Cost (YOC) vs Current Market Yield.
3. Implements the 'Windfall Sweep Rule': Automatically routes excess trading alpha
   and business surplus into the passive 3-Bucket engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class AssetDistributionMeta:
    symbol: str
    annual_yield: float  # e.g. 0.105 for 10.5%
    payout_frequency: int  # 12 for monthly, 4 for quarterly
    tax_treatment: str  # "Section 1256 60/40", "Ordinary", "Qualified Dividend"
    typical_ex_day: int = 20  # day of month


DISTRIBUTION_REGISTRY: dict[str, AssetDistributionMeta] = {
    "SPYI": AssetDistributionMeta("SPYI", 0.112, 12, "Section 1256 60/40", 22),
    "QQQI": AssetDistributionMeta("QQQI", 0.120, 12, "Section 1256 60/40", 22),
    "JEPQ": AssetDistributionMeta("JEPQ", 0.098, 12, "Section 1256 60/40", 1),
    "DIVO": AssetDistributionMeta("DIVO", 0.048, 12, "Qualified Dividend + Options", 20),
    "SGOV": AssetDistributionMeta("SGOV", 0.051, 12, "Ordinary / State-Exempt", 1),
    "USFR": AssetDistributionMeta("USFR", 0.052, 12, "Ordinary / State-Exempt", 1),
    "SCHD": AssetDistributionMeta("SCHD", 0.034, 4, "Qualified Dividend", 20),
    "DGRO": AssetDistributionMeta("DGRO", 0.023, 4, "Qualified Dividend", 15),
}


@dataclass(frozen=True)
class MonthlyCashflowEvent:
    month_index: int
    month_name: str
    symbol: str
    gross_payout_usd: float
    net_payout_usd: float
    tax_rate: float


@dataclass(frozen=True)
class CalendarSummary:
    total_portfolio_value: float
    annual_gross_distributions: float
    annual_net_distributions: float
    average_monthly_net: float
    blended_forward_yield_pct: float
    monthly_breakdown: list[dict[str, Any]] = field(default_factory=list)


class DistributionCalendarEngine:
    """Computes forward cashflow schedules and windfall sweep triggers."""

    MONTH_NAMES = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]

    def __init__(self, registry: Mapping[str, AssetDistributionMeta] | None = None):
        self.registry = dict(DISTRIBUTION_REGISTRY) if registry is None else dict(registry)

    def generate_12_month_calendar(
        self,
        holdings: Mapping[str, float],  # symbol -> market_value_usd
        start_month: int = 1,  # 1 to 12
    ) -> CalendarSummary:
        """Generate month-by-month cashflow projections for the next 12 months."""
        total_value = sum(holdings.values())
        if total_value <= 0:
            return CalendarSummary(
                total_portfolio_value=0.0,
                annual_gross_distributions=0.0,
                annual_net_distributions=0.0,
                average_monthly_net=0.0,
                blended_forward_yield_pct=0.0,
                monthly_breakdown=[],
            )

        monthly_totals: dict[int, dict[str, Any]] = {
            m: {
                "month_index": m,
                "month_name": self.MONTH_NAMES[(m - 1) % 12],
                "gross_usd": 0.0,
                "net_usd": 0.0,
                "events": [],
            }
            for m in range(1, 13)
        }

        total_gross = 0.0
        total_net = 0.0

        for symbol, value in holdings.items():
            meta = self.registry.get(symbol)
            if not meta or value <= 0:
                continue

            annual_gross = value * meta.annual_yield
            tax_rate = (
                0.18
                if "1256" in meta.tax_treatment
                else (0.15 if "Qualified" in meta.tax_treatment else 0.24)
            )
            annual_net = annual_gross * (1.0 - tax_rate)

            total_gross += annual_gross
            total_net += annual_net

            payout_amount_gross = annual_gross / meta.payout_frequency
            payout_amount_net = annual_net / meta.payout_frequency

            for m in range(1, 13):
                # Check if this asset pays in month m
                is_payout_month = False
                if meta.payout_frequency == 12:
                    is_payout_month = True
                elif meta.payout_frequency == 4:
                    # Quarterly in March (3), June (6), September (9), December (12)
                    is_payout_month = m % 3 == 0

                if is_payout_month:
                    monthly_totals[m]["gross_usd"] += payout_amount_gross
                    monthly_totals[m]["net_usd"] += payout_amount_net
                    monthly_totals[m]["events"].append(
                        {
                            "symbol": symbol,
                            "gross_usd": round(payout_amount_gross, 2),
                            "net_usd": round(payout_amount_net, 2),
                        }
                    )

        breakdown = []
        for m in range(1, 13):
            breakdown.append(
                {
                    "month_index": m,
                    "month_name": monthly_totals[m]["month_name"],
                    "gross_usd": round(monthly_totals[m]["gross_usd"], 2),
                    "net_usd": round(monthly_totals[m]["net_usd"], 2),
                    "events_count": len(monthly_totals[m]["events"]),
                }
            )

        return CalendarSummary(
            total_portfolio_value=round(total_value, 2),
            annual_gross_distributions=round(total_gross, 2),
            annual_net_distributions=round(total_net, 2),
            average_monthly_net=round(total_net / 12.0, 2),
            blended_forward_yield_pct=round(total_gross / total_value, 4),
            monthly_breakdown=breakdown,
        )

    def calculate_windfall_sweep(
        self,
        trading_account_equity_usd: float,
        trading_working_capital_cap_usd: float = 25000.0,
        monthly_profit_surplus_usd: float = 0.0,
    ) -> dict[str, Any]:
        """Calculates excess capital to sweep into the passive 3-Bucket foundation."""
        excess_trading_capital = max(
            0.0, trading_account_equity_usd - trading_working_capital_cap_usd
        )
        total_windfall = excess_trading_capital + max(0.0, monthly_profit_surplus_usd)

        return {
            "trading_equity_usd": trading_account_equity_usd,
            "working_capital_cap_usd": trading_working_capital_cap_usd,
            "excess_capital_usd": round(excess_trading_capital, 2),
            "monthly_profit_surplus_usd": round(monthly_profit_surplus_usd, 2),
            "total_windfall_sweep_usd": round(total_windfall, 2),
            "sweep_recommended": total_windfall > 1000.0,
            "suggested_destinations": {
                "bucket_1_liquidity": round(total_windfall * 0.15, 2),
                "bucket_2_cashflow": round(total_windfall * 0.55, 2),
                "bucket_3_compounder": round(total_windfall * 0.30, 2),
            },
        }
