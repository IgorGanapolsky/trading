"""Tests for Section 1256 (60/40) tax treatment.

Covers the defect these functions exist to fix: `src/utils/tax_optimization.py`
taxes a short-held index-option gain at the full short-term rate, which is wrong
for XSP/SPX. The North Star is stated after tax, so that error propagates into
every capital-requirement estimate.
"""

from __future__ import annotations

import pytest

from src.utils.section_1256 import (
    LONG_TERM_TAX_RATE,
    SHORT_TERM_TAX_RATE,
    TaxTreatment,
    after_tax_pnl,
    blended_rate,
    classify_underlying,
    compare_underlyings,
    required_gross_for_after_tax,
)


def test_spy_is_equity_option_not_1256():
    """SPY is an ETF; its options are equity options, not Section 1256."""
    assert classify_underlying("SPY") is TaxTreatment.EQUITY_OPTION


@pytest.mark.parametrize("symbol", ["XSP", "SPX", "SPXW", "NDX", "RUT", "VIX"])
def test_broad_based_indices_are_1256(symbol):
    assert classify_underlying(symbol) is TaxTreatment.SECTION_1256


def test_classification_is_case_and_whitespace_insensitive():
    assert classify_underlying("  xsp ") is TaxTreatment.SECTION_1256


def test_unknown_symbol_defaults_to_higher_tax_treatment():
    """Unknown tickers must NOT be guessed into 1256 -- that understates tax owed."""
    assert classify_underlying("WIDGETCO") is TaxTreatment.EQUITY_OPTION
    assert classify_underlying("") is TaxTreatment.EQUITY_OPTION


def test_1256_blended_rate_is_60_40():
    expected = 0.60 * LONG_TERM_TAX_RATE + 0.40 * SHORT_TERM_TAX_RATE
    assert blended_rate(TaxTreatment.SECTION_1256) == pytest.approx(expected)
    assert blended_rate(TaxTreatment.SECTION_1256) == pytest.approx(0.268)


def test_1256_rate_ignores_holding_period():
    """The statutory 60/40 split does not depend on how long the position was held."""
    one_day = blended_rate(TaxTreatment.SECTION_1256, holding_period_days=1)
    two_years = blended_rate(TaxTreatment.SECTION_1256, holding_period_days=730)
    assert one_day == pytest.approx(two_years)


def test_equity_option_rate_does_depend_on_holding_period():
    assert blended_rate(TaxTreatment.EQUITY_OPTION, holding_period_days=30) == pytest.approx(
        SHORT_TERM_TAX_RATE
    )
    assert blended_rate(TaxTreatment.EQUITY_OPTION, holding_period_days=400) == pytest.approx(
        LONG_TERM_TAX_RATE
    )


def test_short_held_index_gain_is_taxed_less_than_same_spy_gain():
    """The core claim: identical gross gain, held 3 days, XSP nets more than SPY."""
    spy = after_tax_pnl(1000.0, "SPY", holding_period_days=3)
    xsp = after_tax_pnl(1000.0, "XSP", holding_period_days=3)

    assert spy.tax_owed == pytest.approx(370.0)
    assert xsp.tax_owed == pytest.approx(268.0)
    assert xsp.after_tax_pnl > spy.after_tax_pnl
    assert xsp.after_tax_pnl - spy.after_tax_pnl == pytest.approx(102.0)


def test_1256_splits_gain_60_40():
    result = after_tax_pnl(1000.0, "XSP", holding_period_days=3)
    assert result.long_term_portion == pytest.approx(600.0)
    assert result.short_term_portion == pytest.approx(400.0)


def test_1256_is_wash_sale_exempt_and_equity_is_not():
    assert after_tax_pnl(500.0, "XSP").wash_sale_applies is False
    assert after_tax_pnl(500.0, "SPY").wash_sale_applies is True


def test_losses_are_not_taxed():
    loss = after_tax_pnl(-450.0, "XSP", holding_period_days=5)
    assert loss.tax_owed == 0.0
    assert loss.after_tax_pnl == pytest.approx(-450.0)


def test_zero_pnl_is_untaxed():
    flat = after_tax_pnl(0.0, "SPY")
    assert flat.tax_owed == 0.0
    assert flat.after_tax_pnl == 0.0


def test_required_gross_inverts_after_tax_pnl():
    """required_gross_for_after_tax must be the exact inverse of after_tax_pnl."""
    target = 6000.0
    gross = required_gross_for_after_tax(target, "XSP")
    assert after_tax_pnl(gross, "XSP").after_tax_pnl == pytest.approx(target)

    gross_spy = required_gross_for_after_tax(target, "SPY")
    assert after_tax_pnl(gross_spy, "SPY").after_tax_pnl == pytest.approx(target)


def test_north_star_required_gross_figures():
    """The numbers quoted in the module docstring must actually hold."""
    assert required_gross_for_after_tax(6000.0, "SPY") == pytest.approx(9523.81, abs=0.01)
    assert required_gross_for_after_tax(6000.0, "XSP") == pytest.approx(8196.72, abs=0.01)


def test_required_gross_is_zero_for_nonpositive_target():
    assert required_gross_for_after_tax(0.0, "XSP") == 0.0
    assert required_gross_for_after_tax(-100.0, "XSP") == 0.0


def test_required_gross_rejects_confiscatory_rate():
    with pytest.raises(ValueError, match="no after-tax income"):
        required_gross_for_after_tax(100.0, "SPY", short_term_rate=1.0)


def test_compare_quantifies_the_routing_decision():
    out = compare_underlyings(6000.0, "SPY", "XSP")

    assert out["baseline"]["treatment"] == "equity_option"
    assert out["candidate"]["treatment"] == "section_1256"
    assert out["baseline"]["effective_rate"] == pytest.approx(0.37)
    assert out["candidate"]["effective_rate"] == pytest.approx(0.268)
    assert out["gross_saving"] == pytest.approx(1327.09, abs=0.01)
    assert 13.0 < out["gross_saving_pct"] < 15.0
    assert "Not tax advice" in out["disclaimer"]


def test_compare_reports_no_saving_when_both_routes_are_equity():
    out = compare_underlyings(6000.0, "SPY", "QQQ")
    assert out["gross_saving"] == pytest.approx(0.0)
    assert out["gross_saving_pct"] == pytest.approx(0.0)


def test_custom_rates_are_honoured():
    """A lower bracket must flow through both the rate and the requirement."""
    out = after_tax_pnl(1000.0, "XSP", short_term_rate=0.24, long_term_rate=0.15)
    expected_rate = 0.60 * 0.15 + 0.40 * 0.24
    assert out.effective_rate == pytest.approx(expected_rate)
    assert out.tax_owed == pytest.approx(1000.0 * expected_rate)


def test_as_dict_is_json_safe():
    d = after_tax_pnl(1234.56, "XSP", holding_period_days=9).as_dict()
    assert d["treatment"] == "section_1256"
    assert isinstance(d["gross_pnl"], float)
    assert d["wash_sale_applies"] is False
