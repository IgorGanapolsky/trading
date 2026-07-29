import pytest
from src.revenue.ai_ops_affiliate_engine import (
    AIOpsAffiliateEngine,
    ClientAccount,
    PackageTier,
    PACKAGE_CATALOG,
    AFFILIATE_STACK,
)


def test_package_catalog_definitions():
    starter = PACKAGE_CATALOG[PackageTier.STARTER]
    growth = PACKAGE_CATALOG[PackageTier.GROWTH]

    assert starter.setup_fee == 3000.0
    assert starter.monthly_retainer == 1500.0
    assert growth.setup_fee == 5000.0
    assert growth.monthly_retainer == 3000.0


def test_affiliate_mrar_calculation(tmp_path):
    manifest = tmp_path / "clients.json"
    engine = AIOpsAffiliateEngine(manifest_file=manifest)

    # 1 client = HighLevel(297*0.4=118.8) + Resend(97*0.3=29.1) + Perplexity(50*0.2=10.0) = 157.90 MRAR
    mrar_1 = engine.calculate_affiliate_mrar(1)
    assert mrar_1 == 157.90

    mrar_5 = engine.calculate_affiliate_mrar(5)
    assert mrar_5 == 789.50


def test_mercury_trading_allocation():
    engine = AIOpsAffiliateEngine()
    alloc = engine.allocate_to_mercury_trading(10000.0)

    # Gross: $10,000
    # Tax: 20% = $2,000
    # Remainder: $8,000
    # OpEx: $500
    # Surplus: $7,500
    # Alpaca Collateral: 60% of $7,500 = $4,500
    # Profit Sweep: 40% of $7,500 = $3,000
    assert alloc["gross_amount"] == 10000.0
    assert alloc["tax_reserve"] == 2000.0
    assert alloc["opex_reserve"] == 500.0
    assert alloc["alpaca_collateral"] == 4500.0
    assert alloc["profit_sweep"] == 3000.0
