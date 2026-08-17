"""Section 1256 (60/40) tax treatment for broad-based index option structures.

The North Star in `.claude/CLAUDE.md` is stated **after tax**: 6,000 USD/month.
Every P/L number the repo produces is pre-tax, and `src/utils/tax_optimization.py`
classifies gains purely by holding period (short-term under 365 days, long-term
over). That classification is wrong for the instruments this desk actually trades,
and the repo's own rule file already says so:

    .claude/rules/risk-management.md
    "SPY = equity options = 100% short-term capital gains"
    "XSP/SPX = Section 1256 = 60/40 tax treatment, no wash sales"

IRC 26 U.S.C. Section 1256 treats gain on a "non-equity option" -- which includes
options on *broad-based* indices such as SPX and its mini XSP -- as 60% long-term
and 40% short-term **regardless of how long it was held**. A three-day XSP spread
gets the same 60/40 split as one held a year. Section 1256 contracts are also
exempt from the wash-sale rule and are marked to market at year end.

SPY is an ETF, so options on it are *equity* options: ordinary short-term
treatment. XSP tracks the same underlying index at 1/10 the notional of SPX and
is cash-settled, so it is the closest 1256-qualifying substitute for a 1-lot SPY
structure.

Why this is worth wiring up rather than leaving as a comment: the blended rate
gap is not marginal.

    SPY (100% short-term)   : 37.0%
    XSP (Section 1256 60/40): 0.60 * 20% + 0.40 * 37% = 26.8%

To clear the monthly North Star **after tax** you must gross:

    SPY : 6000 / (1 - 0.370) = 9,523.81
    XSP : 6000 / (1 - 0.268) = 8,196.72

That is roughly 1,327 USD/month less gross P/L required for an identical
after-tax result -- about 14% less edge, for no extra capital and no extra risk.
`trading_profiles.py` already registers an XSP variant of the active profile, so
the routing exists; what was missing was the arithmetic to justify using it.

This module is deliberately pure: no I/O, no broker calls, no side effects.

NOT TAX ADVICE. Rates here are top-bracket federal defaults and ignore state tax,
net investment income tax, and individual circumstances. Confirm with a CPA before
filing. Section 1256 positions require Form 6781.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

# Top federal brackets. Deliberately mirrors src/utils/tax_optimization.py so the
# two modules cannot silently disagree about the baseline.
SHORT_TERM_TAX_RATE = 0.37
LONG_TERM_TAX_RATE = 0.20

# Section 1256: 60% long-term / 40% short-term, holding period irrelevant.
SECTION_1256_LONG_TERM_FRACTION = 0.60
SECTION_1256_SHORT_TERM_FRACTION = 0.40

# Broad-based index products whose options qualify as Section 1256 non-equity
# options. ETFs that merely track an index (SPY, QQQ, IWM) do NOT qualify --
# they are equity options. Keep this list conservative: a wrong entry here
# understates tax owed, which is the dangerous direction to be wrong in.
SECTION_1256_UNDERLYINGS: frozenset[str] = frozenset(
    {
        "SPX",
        "SPXW",
        "XSP",
        "NDX",
        "XND",
        "RUT",
        "VIX",
        "DJX",
    }
)


class TaxTreatment(StrEnum):
    """How a realized options gain is characterized for tax."""

    EQUITY_OPTION = "equity_option"  # holding-period based, wash sales apply
    SECTION_1256 = "section_1256"  # fixed 60/40, wash-sale exempt, MTM


@dataclass(frozen=True)
class AfterTaxResult:
    """After-tax outcome for a realized gain under one treatment."""

    underlying: str
    treatment: TaxTreatment
    gross_pnl: float
    tax_owed: float
    after_tax_pnl: float
    effective_rate: float
    long_term_portion: float
    short_term_portion: float
    wash_sale_applies: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "underlying": self.underlying,
            "treatment": self.treatment.value,
            "gross_pnl": round(self.gross_pnl, 2),
            "tax_owed": round(self.tax_owed, 2),
            "after_tax_pnl": round(self.after_tax_pnl, 2),
            "effective_rate": round(self.effective_rate, 6),
            "long_term_portion": round(self.long_term_portion, 2),
            "short_term_portion": round(self.short_term_portion, 2),
            "wash_sale_applies": self.wash_sale_applies,
        }


def classify_underlying(underlying: str) -> TaxTreatment:
    """Return the tax treatment for options on ``underlying``.

    Unknown symbols default to EQUITY_OPTION -- the higher-tax, more conservative
    assumption. Guessing 1256 on an unrecognized ticker would understate tax owed.
    """
    symbol = str(underlying or "").strip().upper()
    if symbol in SECTION_1256_UNDERLYINGS:
        return TaxTreatment.SECTION_1256
    return TaxTreatment.EQUITY_OPTION


def blended_rate(
    treatment: TaxTreatment,
    *,
    holding_period_days: int | None = None,
    short_term_rate: float = SHORT_TERM_TAX_RATE,
    long_term_rate: float = LONG_TERM_TAX_RATE,
) -> float:
    """Effective tax rate on a gain under ``treatment``.

    For SECTION_1256 the holding period is ignored by statute. For EQUITY_OPTION
    a holding period of 365+ days earns the long-term rate; anything shorter (or
    unknown) is short-term.
    """
    if treatment is TaxTreatment.SECTION_1256:
        return (
            SECTION_1256_LONG_TERM_FRACTION * long_term_rate
            + SECTION_1256_SHORT_TERM_FRACTION * short_term_rate
        )
    if holding_period_days is not None and holding_period_days >= 365:
        return long_term_rate
    return short_term_rate


def after_tax_pnl(
    gross_pnl: float,
    underlying: str,
    *,
    holding_period_days: int | None = None,
    short_term_rate: float = SHORT_TERM_TAX_RATE,
    long_term_rate: float = LONG_TERM_TAX_RATE,
) -> AfterTaxResult:
    """After-tax outcome for a realized gain or loss.

    Losses are returned untaxed (``tax_owed`` 0.0). Netting a loss against other
    gains, the ordinary-income deduction cap, and Section 1256 loss carryback all
    depend on the rest of the return and are handled in
    ``src/utils/tax_optimization.py``, not here.
    """
    treatment = classify_underlying(underlying)
    rate = blended_rate(
        treatment,
        holding_period_days=holding_period_days,
        short_term_rate=short_term_rate,
        long_term_rate=long_term_rate,
    )
    symbol = str(underlying or "").strip().upper()

    if gross_pnl <= 0:
        return AfterTaxResult(
            underlying=symbol,
            treatment=treatment,
            gross_pnl=gross_pnl,
            tax_owed=0.0,
            after_tax_pnl=gross_pnl,
            effective_rate=0.0,
            long_term_portion=0.0,
            short_term_portion=0.0,
            wash_sale_applies=treatment is TaxTreatment.EQUITY_OPTION,
        )

    if treatment is TaxTreatment.SECTION_1256:
        long_portion = gross_pnl * SECTION_1256_LONG_TERM_FRACTION
        short_portion = gross_pnl * SECTION_1256_SHORT_TERM_FRACTION
    elif holding_period_days is not None and holding_period_days >= 365:
        long_portion, short_portion = gross_pnl, 0.0
    else:
        long_portion, short_portion = 0.0, gross_pnl

    tax = long_portion * long_term_rate + short_portion * short_term_rate

    return AfterTaxResult(
        underlying=symbol,
        treatment=treatment,
        gross_pnl=gross_pnl,
        tax_owed=tax,
        after_tax_pnl=gross_pnl - tax,
        effective_rate=rate,
        long_term_portion=long_portion,
        short_term_portion=short_portion,
        wash_sale_applies=treatment is TaxTreatment.EQUITY_OPTION,
    )


def required_gross_for_after_tax(
    target_after_tax: float,
    underlying: str,
    *,
    holding_period_days: int | None = None,
    short_term_rate: float = SHORT_TERM_TAX_RATE,
    long_term_rate: float = LONG_TERM_TAX_RATE,
) -> float:
    """Gross P/L needed to net ``target_after_tax`` on ``underlying``.

    This is the number the North Star actually requires. Quoting a monthly P/L
    goal without it understates the necessary edge by the full tax drag.
    """
    if target_after_tax <= 0:
        return 0.0
    rate = blended_rate(
        classify_underlying(underlying),
        holding_period_days=holding_period_days,
        short_term_rate=short_term_rate,
        long_term_rate=long_term_rate,
    )
    if rate >= 1.0:
        raise ValueError(f"effective tax rate {rate} leaves no after-tax income")
    return target_after_tax / (1.0 - rate)


def _route_view(
    underlying: str,
    target_after_tax: float,
    short_term_rate: float,
    long_term_rate: float,
) -> dict[str, object]:
    treatment = classify_underlying(underlying)
    return {
        "underlying": underlying.strip().upper(),
        "treatment": treatment.value,
        "effective_rate": round(
            blended_rate(
                treatment,
                short_term_rate=short_term_rate,
                long_term_rate=long_term_rate,
            ),
            6,
        ),
        "required_gross": round(
            required_gross_for_after_tax(
                target_after_tax,
                underlying,
                short_term_rate=short_term_rate,
                long_term_rate=long_term_rate,
            ),
            2,
        ),
    }


def compare_underlyings(
    target_after_tax: float,
    baseline: str = "SPY",
    candidate: str = "XSP",
    *,
    short_term_rate: float = SHORT_TERM_TAX_RATE,
    long_term_rate: float = LONG_TERM_TAX_RATE,
) -> dict[str, object]:
    """Quantify the tax-routing decision between two underlyings.

    Returns the gross P/L each route needs to hit the same after-tax target, and
    the saving from the candidate. Structure risk is comparable (same index
    exposure, same defined-risk spread), so the difference is tax drag.
    """
    baseline_view = _route_view(baseline, target_after_tax, short_term_rate, long_term_rate)
    candidate_view = _route_view(candidate, target_after_tax, short_term_rate, long_term_rate)

    baseline_gross = float(baseline_view["required_gross"])
    candidate_gross = float(candidate_view["required_gross"])
    saving = baseline_gross - candidate_gross

    return {
        "target_after_tax": round(target_after_tax, 2),
        "baseline": baseline_view,
        "candidate": candidate_view,
        "gross_saving": round(saving, 2),
        "gross_saving_pct": round(saving / baseline_gross * 100.0, 4) if baseline_gross else 0.0,
        "disclaimer": (
            "Top-bracket federal rates only; excludes state tax, NIIT, and personal "
            "circumstances. Section 1256 positions require Form 6781. Not tax advice. "
            "This changes tax treatment only -- it does not create trading edge, and "
            "live capital remains blocked until the paper cohort clears kill criteria."
        ),
    }
