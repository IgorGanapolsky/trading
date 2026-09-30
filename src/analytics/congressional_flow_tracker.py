"""Congressional Committee Conflict & Unusual Options Flow Tracker.

Reverse-engineers and expands institutional retail intel (inspired by Unusual Whales):
1. Cross-references politician stock and option trades against Congressional committee jurisdictions
   (Armed Services, Financial Services, Energy & Commerce, Intelligence).
2. Computes empirical conflict scores based on committee oversight and transaction size.
3. Applies exponential disclosure decay models to account for 30-45 day STOCK Act filing lags.
4. Fuses politician directional flow with institutional Unusual Options Activity (sweeps/blocks)
   and dealer Gamma Exposure (GEX) regimes from options_vol_gex.py.
5. Emits actionable, type-safe alpha signals with transparent audit rationale.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal, Mapping

Chamber = Literal["house", "senate"]
Party = Literal["D", "R", "I"]
TransactionType = Literal["purchase", "sale"]
TradeAction = Literal["BUY_CALL_SPREAD", "BUY_PUT_SPREAD", "SELL_PUT_CREDIT", "NEUTRAL_HOLD"]

# Canonical Committee Jurisdiction Mapping to Ticker Sectors
COMMITTEE_JURISDICTIONS: Mapping[str, frozenset[str]] = {
    "Armed Services": frozenset(
        {
            "LMT",
            "RTX",
            "GD",
            "BA",
            "NOC",
            "HII",
            "PLTR",
            "KTOS",
            "LHX",
            "TXT",
            "LDOS",
            "SAIC",
            "CACI",
        }
    ),
    "Energy and Commerce": frozenset(
        {
            "XOM",
            "CVX",
            "COP",
            "SLB",
            "OXY",
            "EOG",
            "VLO",
            "PSX",
            "MPC",
            "NVDA",
            "INTC",
            "TSM",
            "AMD",
            "QCOM",
            "AVGO",
            "AMAT",
            "MU",
            "PFE",
            "MRK",
            "ABBV",
            "LLY",
            "BMY",
            "UNH",
            "CVS",
        }
    ),
    "Financial Services": frozenset(
        {
            "JPM",
            "BAC",
            "GS",
            "MS",
            "C",
            "WFC",
            "V",
            "MA",
            "COIN",
            "BLK",
            "SCHW",
            "AXP",
            "PYPL",
            "HOOD",
            "MCO",
            "SPGI",
        }
    ),
    "Banking, Housing, and Urban Affairs": frozenset(
        {
            "JPM",
            "BAC",
            "GS",
            "MS",
            "C",
            "WFC",
            "V",
            "MA",
            "COIN",
            "BLK",
            "SCHW",
            "AXP",
            "O",
            "PLD",
            "EQIX",
            "AMT",
        }
    ),
    "Intelligence": frozenset(
        {
            "PLTR",
            "PANW",
            "CRWD",
            "FTNT",
            "NET",
            "MSFT",
            "GOOGL",
            "AMZN",
            "CSCO",
            "ORCL",
            "SNOW",
            "ZS",
        }
    ),
    "Agriculture": frozenset(
        {
            "DE",
            "ADM",
            "MOS",
            "NTR",
            "CF",
            "BG",
            "CTVA",
            "FMC",
        }
    ),
    "Transportation and Infrastructure": frozenset(
        {
            "UNP",
            "CSX",
            "NSC",
            "FDX",
            "UPS",
            "DAL",
            "UAL",
            "AAL",
            "LUV",
            "CAT",
            "URI",
            "VMC",
            "MLM",
        }
    ),
}

# Known key Congressional members and their committee rosters
POLITICIAN_ROSTER: Mapping[str, tuple[str, ...]] = {
    "Nancy Pelosi": (
        "Energy and Commerce",
        "Intelligence",
    ),
    "Tommy Tuberville": (
        "Armed Services",
        "Agriculture",
    ),
    "Dan Crenshaw": (
        "Energy and Commerce",
        "Intelligence",
    ),
    "Michael McCaul": (
        "Armed Services",
        "Intelligence",
    ),
    "Ro Khanna": ("Armed Services",),
    "Josh Gottheimer": (
        "Financial Services",
        "Intelligence",
    ),
    "Markwayne Mullin": ("Armed Services",),
}


@dataclass(frozen=True)
class PoliticianTrade:
    """A disclosed transaction by a member of the United States Congress."""

    ticker: str
    politician: str
    chamber: Chamber
    party: Party
    transaction_type: TransactionType
    trade_date: str
    disclosure_date: str
    amount_min: float
    amount_max: float
    committees: tuple[str, ...] = ()
    asset_description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "ticker", self.ticker.upper().strip())
        if not self.committees:
            default_committees = POLITICIAN_ROSTER.get(self.politician, ())
            object.__setattr__(self, "committees", default_committees)


@dataclass(frozen=True)
class OptionsFlowSignal:
    """An unusual options block or sweep activity observation."""

    ticker: str
    option_type: Literal["call", "put"]
    strike: float
    expiration: str
    premium: float
    volume_oi_ratio: float
    side: Literal["ask", "bid", "mid"]
    sweep: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "ticker", self.ticker.upper().strip())


@dataclass(frozen=True)
class CongressionalAlphaSignal:
    """Synthesized alpha decision merging Congressional conflicts, decay, and flow."""

    ticker: str
    action: TradeAction
    confidence: float
    conflict_score: float
    jurisdiction_matches: tuple[str, ...]
    disclosure_decay: float
    flow_confirmation: bool
    flow_details: Mapping[str, Any] | None
    gex_regime: str | None
    composite_score: float
    rationale: str


def calculate_disclosure_decay(
    trade_date_str: str,
    disclosure_date_str: str,
    half_life_days: float = 30.0,
) -> float:
    """Compute exponential decay factor reflecting informational shelf-life.

    STOCK Act disclosures carry a 30-45 day statutory delay. Fresh disclosures
    retain maximum alpha value; older disclosures decay towards zero.
    """
    try:
        t_date = date.fromisoformat(trade_date_str)
        d_date = date.fromisoformat(disclosure_date_str)
        delay_days = max(0, (d_date - t_date).days)
    except (ValueError, TypeError):
        delay_days = 30

    if half_life_days <= 0:
        return 0.0

    decay = math.pow(0.5, delay_days / half_life_days)
    return round(max(0.05, min(1.0, decay)), 4)


def evaluate_committee_conflict(trade: PoliticianTrade) -> tuple[float, tuple[str, ...]]:
    """Determine whether politician's committee assignments overlap with ticker jurisdiction."""
    matched_committees: list[str] = []
    symbol = trade.ticker

    for comm in trade.committees:
        # Match normalized committee name against jurisdiction keys
        for key, tickers in COMMITTEE_JURISDICTIONS.items():
            if (key.lower() in comm.lower() or comm.lower() in key.lower()) and symbol in tickers:
                matched_committees.append(key)

    unique_matches = tuple(sorted(set(matched_committees)))

    if unique_matches:
        # High conflict: base 0.80 + transaction size weighting
        avg_amount = (trade.amount_min + trade.amount_max) / 2.0
        size_boost = min(0.15, (avg_amount / 500_000.0) * 0.15)
        score = round(min(1.0, 0.80 + size_boost), 4)
    else:
        score = 0.20

    return score, unique_matches


def analyze_congressional_flow(
    trade: PoliticianTrade,
    flow: OptionsFlowSignal | None = None,
    gex_regime: str | None = None,
) -> CongressionalAlphaSignal:
    """Synthesize Congressional insider conflict, disclosure decay, and options flow."""
    conflict_score, matches = evaluate_committee_conflict(trade)
    decay = calculate_disclosure_decay(trade.trade_date, trade.disclosure_date)

    # Base confidence: product of conflict relevance and disclosure freshness
    base_confidence = conflict_score * decay

    flow_confirmed = False
    flow_meta: dict[str, Any] | None = None
    flow_multiplier = 1.0

    if flow and flow.ticker == trade.ticker:
        # Flow alignment check: call flow confirms purchase; put flow confirms sale
        is_bullish_flow = (
            flow.option_type == "call"
            and flow.side == "ask"
            and flow.premium >= 250_000
            and flow.volume_oi_ratio >= 1.5
        )
        is_bearish_flow = (
            flow.option_type == "put"
            and flow.side == "ask"
            and flow.premium >= 250_000
            and flow.volume_oi_ratio >= 1.5
        )

        flow_meta = {
            "option_type": flow.option_type,
            "strike": flow.strike,
            "expiration": flow.expiration,
            "premium": flow.premium,
            "volume_oi_ratio": flow.volume_oi_ratio,
            "sweep": flow.sweep,
            "side": flow.side,
        }

        if (
            trade.transaction_type == "purchase"
            and is_bullish_flow
            or trade.transaction_type == "sale"
            and is_bearish_flow
        ):
            flow_confirmed = True
            flow_multiplier = 1.35 if flow.sweep else 1.20

    # GEX regime alignment multiplier
    gex_multiplier = 1.0
    if gex_regime == "negative_gamma":
        # Negative gamma accelerates directional trends (breakout friendly)
        gex_multiplier = 1.15
    elif gex_regime == "positive_gamma":
        # Positive gamma dampens volatility (favorable for credit spreads)
        gex_multiplier = 1.05

    composite = min(1.0, base_confidence * flow_multiplier * gex_multiplier)
    composite = round(composite, 4)

    # Decision Matrix
    action: TradeAction
    if composite >= 0.50:
        if trade.transaction_type == "purchase":
            if gex_regime == "positive_gamma":
                action = "SELL_PUT_CREDIT"
            else:
                action = "BUY_CALL_SPREAD"
        else:
            action = "BUY_PUT_SPREAD"
    else:
        action = "NEUTRAL_HOLD"

    rationale_parts = [
        f"Politician {trade.politician} ({trade.party}-{trade.chamber.upper()}) {trade.transaction_type.upper()} {trade.ticker}.",
        f"Conflict score: {conflict_score:.2f} (Jurisdiction: {', '.join(matches) if matches else 'None'}).",
        f"Disclosure decay: {decay:.2f}.",
    ]
    if flow_confirmed:
        rationale_parts.append(
            f"Institutional {flow.option_type.upper()} flow confirmed: ${flow.premium:,.0f} "
            f"(Vol/OI {flow.volume_oi_ratio:.1f}x, Sweep={flow.sweep})."
        )
    if gex_regime:
        rationale_parts.append(f"Dealer GEX regime: {gex_regime}.")
    rationale_parts.append(f"Composite conviction: {composite:.2f} -> {action}.")

    return CongressionalAlphaSignal(
        ticker=trade.ticker,
        action=action,
        confidence=round(base_confidence, 4),
        conflict_score=conflict_score,
        jurisdiction_matches=matches,
        disclosure_decay=decay,
        flow_confirmation=flow_confirmed,
        flow_details=flow_meta,
        gex_regime=gex_regime,
        composite_score=composite,
        rationale=" ".join(rationale_parts),
    )
