"""
Tests for P/L Validator.

Ensures that:
1. Non-allowed trades (non-SPY/SPX/XSP) are flagged as violations
2. SPY/SPX/XSP iron condor legs are classified correctly
3. Projections are blocked with insufficient data
4. P/L decomposition separates compliant from violating orders
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.pl_validator import (
    classify_order,
    count_completed_iron_condors,
    extract_base_ticker,
    format_pl_report,
    is_spy_option,
    validate_pl_report,
)


class TestExtractBaseTicker:
    def test_spy_option(self):
        assert extract_base_ticker("SPY260220P00660000") == "SPY"

    def test_aapl_option(self):
        assert extract_base_ticker("AAPL260220P00430000") == "AAPL"

    def test_plain_ticker(self):
        assert extract_base_ticker("SPY") == "SPY"

    def test_crypto(self):
        assert extract_base_ticker("BTC/USD") == "BTC/USD"


class TestIsSpyOption:
    def test_spy_put(self):
        assert is_spy_option("SPY260220P00660000") is True

    def test_spy_call(self):
        assert is_spy_option("SPY260313C00725000") is True

    def test_spx_put(self):
        assert is_spy_option("SPX260220P00660000") is True

    def test_spx_call(self):
        assert is_spy_option("SPX260313C00725000") is True

    def test_xsp_put(self):
        assert is_spy_option("XSP260220P00066000") is True

    def test_xsp_call(self):
        assert is_spy_option("XSP260313C00072500") is True

    def test_aapl_option(self):
        assert is_spy_option("AAPL260220P00430000") is False

    def test_spy_stock(self):
        assert is_spy_option("SPY") is False

    def test_crypto(self):
        assert is_spy_option("BTC/USD") is False


class TestClassifyOrder:
    def test_spy_option_is_compliant(self):
        order = {
            "symbol": "SPY260220P00660000",
            "side": "buy",
            "qty": "1",
            "filled_avg_price": "1.62",
            "created_at": "2026-02-06T18:48:00Z",
        }
        result = classify_order(order)
        assert result.is_spy_option is True
        assert result.is_iron_condor_leg is True
        assert result.violation_reason == ""

    def test_spx_option_is_compliant(self):
        order = {
            "symbol": "SPX260220P00660000",
            "side": "buy",
            "qty": "1",
            "filled_avg_price": "16.20",
            "created_at": "2026-02-06T18:48:00Z",
        }
        result = classify_order(order)
        assert result.is_spy_option is True
        assert result.is_iron_condor_leg is True
        assert result.violation_reason == ""

    def test_xsp_option_is_compliant(self):
        order = {
            "symbol": "XSP260220P00066000",
            "side": "sell",
            "qty": "1",
            "filled_avg_price": "1.26",
            "created_at": "2026-02-06T18:48:00Z",
        }
        result = classify_order(order)
        assert result.is_spy_option is True
        assert result.is_iron_condor_leg is True
        assert result.violation_reason == ""

    def test_aapl_option_is_violation(self):
        order = {
            "symbol": "AAPL260220P00430000",
            "side": "buy",
            "qty": "1",
            "filled_avg_price": "160.15",
            "created_at": "2026-02-03T14:57:00Z",
        }
        result = classify_order(order)
        assert result.is_spy_option is False
        assert result.violation_reason == "Non-allowed option (AAPL)"

    def test_spy_stock_is_violation(self):
        order = {
            "symbol": "SPY",
            "side": "sell",
            "qty": "36.477",
            "filled_avg_price": "686.58",
            "created_at": "2026-02-03T18:17:00Z",
        }
        result = classify_order(order)
        assert result.violation_reason == "SPY stock trade (not an iron condor option)"

    def test_crypto_is_violation(self):
        order = {
            "symbol": "BTC/USD",
            "side": "buy",
            "qty": "0.001",
            "filled_avg_price": "45000",
            "created_at": "2025-12-10T00:00:00Z",
        }
        result = classify_order(order)
        assert result.violation_reason == "Non-allowed instrument: BTC/USD"

    def test_reit_is_violation(self):
        order = {
            "symbol": "DLR",
            "side": "sell",
            "qty": "0.084",
            "filled_avg_price": "165.21",
            "created_at": "2026-02-03T14:00:00Z",
        }
        result = classify_order(order)
        assert result.violation_reason == "Non-allowed instrument: DLR"

    def test_sofi_option_is_violation(self):
        order = {
            "symbol": "SOFI260206P00024000",
            "side": "sell",
            "qty": "1",
            "filled_avg_price": "0.32",
            "created_at": "2026-01-07T15:53:00Z",
        }
        result = classify_order(order)
        assert result.violation_reason == "Non-allowed option (SOFI)"


class TestCountCompletedIronCondors:
    def test_four_legs_same_minute_is_condor(self):
        orders = [
            {
                "symbol": "SPY260220P00660000",
                "side": "buy",
                "created_at": "2026-02-06T18:48",
                "status": "filled",
            },
            {
                "symbol": "SPY260220P00655000",
                "side": "sell",
                "created_at": "2026-02-06T18:48",
                "status": "filled",
            },
            {
                "symbol": "SPY260220C00725000",
                "side": "sell",
                "created_at": "2026-02-06T18:48",
                "status": "filled",
            },
            {
                "symbol": "SPY260220C00720000",
                "side": "buy",
                "created_at": "2026-02-06T18:48",
                "status": "filled",
            },
        ]
        assert count_completed_iron_condors(orders) == 1

    def test_two_legs_is_not_condor(self):
        orders = [
            {
                "symbol": "SPY260220P00660000",
                "side": "buy",
                "created_at": "2026-02-06T18:48",
                "status": "filled",
            },
            {
                "symbol": "SPY260220P00655000",
                "side": "sell",
                "created_at": "2026-02-06T18:48",
                "status": "filled",
            },
        ]
        assert count_completed_iron_condors(orders) == 0

    def test_non_spy_options_not_counted(self):
        orders = [
            {
                "symbol": "AAPL260220P00430000",
                "side": "buy",
                "created_at": "2026-02-06T18:48",
                "status": "filled",
            },
            {
                "symbol": "AAPL260220P00425000",
                "side": "sell",
                "created_at": "2026-02-06T18:48",
                "status": "filled",
            },
            {
                "symbol": "AAPL260220C00450000",
                "side": "sell",
                "created_at": "2026-02-06T18:48",
                "status": "filled",
            },
            {
                "symbol": "AAPL260220C00455000",
                "side": "buy",
                "created_at": "2026-02-06T18:48",
                "status": "filled",
            },
        ]
        assert count_completed_iron_condors(orders) == 0

    def test_unfilled_not_counted(self):
        orders = [
            {
                "symbol": "SPY260220P00660000",
                "side": "buy",
                "created_at": "2026-02-06T18:48",
                "status": "canceled",
            },
            {
                "symbol": "SPY260220P00655000",
                "side": "sell",
                "created_at": "2026-02-06T18:48",
                "status": "canceled",
            },
            {
                "symbol": "SPY260220C00725000",
                "side": "sell",
                "created_at": "2026-02-06T18:48",
                "status": "canceled",
            },
            {
                "symbol": "SPY260220C00720000",
                "side": "buy",
                "created_at": "2026-02-06T18:48",
                "status": "canceled",
            },
        ]
        assert count_completed_iron_condors(orders) == 0


class TestValidatePLReport:
    def test_mixed_orders_decomposed(self):
        orders = [
            # Compliant: SPY iron condor leg
            {
                "symbol": "SPY260220P00660000",
                "side": "buy",
                "qty": "1",
                "filled_avg_price": "1.62",
                "created_at": "2026-02-06T18:48",
                "status": "filled",
            },
            # Violation: AAPL option
            {
                "symbol": "AAPL260220P00430000",
                "side": "buy",
                "qty": "1",
                "filled_avg_price": "160.15",
                "created_at": "2026-02-03T14:57",
                "status": "filled",
            },
            # Violation: crypto
            {
                "symbol": "BTC/USD",
                "side": "buy",
                "qty": "0.001",
                "filled_avg_price": "45000",
                "created_at": "2025-12-10T00:00",
                "status": "filled",
            },
        ]
        report = validate_pl_report(orders, current_equity=101440.13, starting_equity=100000.0)

        assert report.total_pl == pytest.approx(1440.13)
        assert len(report.compliant_orders) == 1
        assert len(report.violating_orders) == 2
        assert report.can_project is False

    def test_projection_blocked_under_30_trades(self):
        # 2 iron condors = 8 legs, but only 2 completed condors
        orders = []
        for minute in ["18:48", "19:00"]:
            orders.extend(
                [
                    {
                        "symbol": "SPY260220P00660000",
                        "side": "buy",
                        "qty": "1",
                        "filled_avg_price": "1.62",
                        "created_at": f"2026-02-06T{minute}",
                        "status": "filled",
                    },
                    {
                        "symbol": "SPY260220P00655000",
                        "side": "sell",
                        "qty": "1",
                        "filled_avg_price": "1.26",
                        "created_at": f"2026-02-06T{minute}",
                        "status": "filled",
                    },
                    {
                        "symbol": "SPY260220C00725000",
                        "side": "sell",
                        "qty": "1",
                        "filled_avg_price": "0.05",
                        "created_at": f"2026-02-06T{minute}",
                        "status": "filled",
                    },
                    {
                        "symbol": "SPY260220C00720000",
                        "side": "buy",
                        "qty": "1",
                        "filled_avg_price": "0.09",
                        "created_at": f"2026-02-06T{minute}",
                        "status": "filled",
                    },
                ]
            )
        report = validate_pl_report(orders, current_equity=101000.0, starting_equity=100000.0)
        assert report.completed_iron_condors == 2
        assert report.can_project is False

    def test_no_violations_with_only_spy_options(self):
        orders = [
            {
                "symbol": "SPY260220P00660000",
                "side": "buy",
                "qty": "1",
                "filled_avg_price": "1.62",
                "created_at": "2026-02-06T18:48",
                "status": "filled",
            },
        ]
        report = validate_pl_report(orders, current_equity=100100.0, starting_equity=100000.0)
        assert len(report.violating_orders) == 0
        assert report.violations_summary == ""

    def test_unfilled_orders_ignored(self):
        orders = [
            {
                "symbol": "AAPL260220P00430000",
                "side": "buy",
                "qty": "1",
                "filled_avg_price": None,
                "created_at": "2026-02-03T14:57",
                "status": "canceled",
            },
        ]
        report = validate_pl_report(orders, current_equity=100000.0, starting_equity=100000.0)
        assert len(report.violating_orders) == 0
        assert len(report.compliant_orders) == 0


class TestFormatPLReport:
    def test_format_includes_projection_warning(self):
        orders = [
            {
                "symbol": "SPY260220P00660000",
                "side": "buy",
                "qty": "1",
                "filled_avg_price": "1.62",
                "created_at": "2026-02-06T18:48",
                "status": "filled",
            },
        ]
        report = validate_pl_report(orders, current_equity=101440.0, starting_equity=100000.0)
        formatted = format_pl_report(report)
        assert "Projection BLOCKED" in formatted
        assert "0/30" in formatted

    def test_format_includes_violations(self):
        orders = [
            {
                "symbol": "SOFI260206P00024000",
                "side": "sell",
                "qty": "1",
                "filled_avg_price": "0.32",
                "created_at": "2026-01-07T15:53",
                "status": "filled",
            },
        ]
        report = validate_pl_report(orders, current_equity=100000.0, starting_equity=100000.0)
        formatted = format_pl_report(report)
        assert "Rule Violations" in formatted
        assert "SOFI" in formatted


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
