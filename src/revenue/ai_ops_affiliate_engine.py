"""Productized Autonomous AI Ops & Software Affiliate Revenue Engine.

Implements Shaan Puri's $0-to-$1M framework:
1. Package Configuration (Starter, Growth, Enterprise DFY Agent Packages)
2. Embedded Software Stack Affiliate Tracking (30-40% recurring commissions)
3. Mercury Bank Cash Flow Routing to Alpaca Options Collateral
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
CLIENT_MANIFEST_FILE = ROOT / "data" / "revenue" / "ai_ops_clients_manifest.json"


class PackageTier(str, Enum):
    STARTER = "STARTER"
    GROWTH = "GROWTH"
    ENTERPRISE = "ENTERPRISE"


@dataclass(frozen=True)
class PackageDefinition:
    tier: PackageTier
    setup_fee: float
    monthly_retainer: float
    dfy_agents: tuple[str, ...]
    estimated_client_mrr_boost: float


PACKAGE_CATALOG: dict[PackageTier, PackageDefinition] = {
    PackageTier.STARTER: PackageDefinition(
        tier=PackageTier.STARTER,
        setup_fee=3000.0,
        monthly_retainer=1500.0,
        dfy_agents=("Outbound SDR Agent", "Lead Enrichment Agent"),
        estimated_client_mrr_boost=5000.0,
    ),
    PackageTier.GROWTH: PackageDefinition(
        tier=PackageTier.GROWTH,
        setup_fee=5000.0,
        monthly_retainer=3000.0,
        dfy_agents=("Outbound SDR Agent", "Appointment Setter Agent", "CRM Sync Agent"),
        estimated_client_mrr_boost=15000.0,
    ),
    PackageTier.ENTERPRISE: PackageDefinition(
        tier=PackageTier.ENTERPRISE,
        setup_fee=10000.0,
        monthly_retainer=5000.0,
        dfy_agents=(
            "Outbound SDR Agent",
            "Appointment Setter Agent",
            "RAG Knowledge Base Agent",
            "Executive Reporting Agent",
        ),
        estimated_client_mrr_boost=35000.0,
    ),
}


@dataclass(frozen=True)
class AffiliateTool:
    name: str
    category: str
    monthly_cost_per_client: float
    commission_rate: float  # e.g., 0.30 = 30%
    affiliate_url: str


AFFILIATE_STACK: tuple[AffiliateTool, ...] = (
    AffiliateTool(
        name="HighLevel / GoHighLevel",
        category="CRM & Outbound",
        monthly_cost_per_client=297.0,
        commission_rate=0.40,
        affiliate_url="https://gohighlevel.com/?fp_ref=igor_trading",
    ),
    AffiliateTool(
        name="Resend / Instantly Email",
        category="Email Automation",
        monthly_cost_per_client=97.0,
        commission_rate=0.30,
        affiliate_url="https://instantly.ai/?via=igor_trading",
    ),
    AffiliateTool(
        name="Perplexity API Gateway",
        category="Research Engine",
        monthly_cost_per_client=50.0,
        commission_rate=0.20,
        affiliate_url="https://perplexity.ai/?ref=igor_trading",
    ),
)


@dataclass
class ClientAccount:
    client_id: str
    company_name: str
    tier: PackageTier
    active: bool
    setup_paid: bool
    months_active: int


class AIOpsAffiliateEngine:
    """Manages AI Ops client packaging, affiliate MRR projections, and revenue routing."""

    def __init__(self, manifest_file: Path | None = None):
        self.manifest_path = manifest_file or CLIENT_MANIFEST_FILE
        self.clients: list[ClientAccount] = self._load_clients()

    def _load_clients(self) -> list[ClientAccount]:
        if self.manifest_path.exists():
            try:
                with self.manifest_path.open("r", encoding="utf-8") as h:
                    data = json.load(h)
                    return [
                        ClientAccount(
                            client_id=c["client_id"],
                            company_name=c["company_name"],
                            tier=PackageTier(c["tier"]),
                            active=c["active"],
                            setup_paid=c["setup_paid"],
                            months_active=c["months_active"],
                        )
                        for c in data.get("clients", [])
                    ]
            except Exception as e:
                logger.warning("Failed to load client manifest: %s", e)
        return []

    def calculate_affiliate_mrar(self, active_client_count: int) -> float:
        """Calculates Monthly Recurring Affiliate Revenue (MRAR) for active client count."""
        per_client_commission = sum(
            tool.monthly_cost_per_client * tool.commission_rate for tool in AFFILIATE_STACK
        )
        return round(per_client_commission * active_client_count, 2)

    def calculate_total_monthly_revenue(self) -> dict[str, float]:
        active_clients = [c for c in self.clients if c.active]
        retainer_revenue = sum(PACKAGE_CATALOG[c.tier].monthly_retainer for c in active_clients)
        affiliate_mrar = self.calculate_affiliate_mrar(len(active_clients))
        total_monthly = retainer_revenue + affiliate_mrar

        return {
            "active_client_count": len(active_clients),
            "retainer_revenue": retainer_revenue,
            "affiliate_mrar": affiliate_mrar,
            "total_monthly_revenue": total_monthly,
        }

    def allocate_to_mercury_trading(self, gross_amount: float) -> dict[str, float]:
        """Routes gross revenue through Mercury Bank auto-allocation ratios."""
        tax_reserve = round(gross_amount * 0.20, 2)
        rem = max(0.0, gross_amount - tax_reserve)

        opex_reserve = 500.0 if rem >= 500.0 else rem
        surplus = max(0.0, rem - opex_reserve)

        alpaca_collateral = round(surplus * 0.60, 2)
        profit_sweep = round(surplus * 0.40, 2)

        return {
            "gross_amount": gross_amount,
            "tax_reserve": tax_reserve,
            "opex_reserve": opex_reserve,
            "alpaca_collateral": alpaca_collateral,
            "profit_sweep": profit_sweep,
        }
