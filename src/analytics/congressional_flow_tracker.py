"""Congressional Committee Conflict & Unusual Options Flow Tracker.

Reverse-engineers and expands institutional retail intel (inspired by Unusual Whales):
1. Cross-references politician stock and option trades against Congressional committee jurisdictions
   (Armed Services, Financial Services, Energy & Commerce, Intelligence, Foreign Affairs, Homeland Security).
2. Computes empirical conflict scores based on committee oversight and transaction size.
3. Applies exponential disclosure decay models to account for filing delays and post-disclosure aging.
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
InstrumentType = Literal["stock", "call_option", "put_option", "other"]
TradeDirection = Literal["bullish", "bearish", "neutral"]
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
    "Foreign Affairs": frozenset(
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
        }
    ),
    "Homeland Security": frozenset(
        {
            "PLTR",
            "PANW",
            "CRWD",
            "FTNT",
            "NET",
            "CSCO",
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

# Committee aliases for robust normalization
COMMITTEE_ALIASES: Mapping[str, str] = {
    "armed services": "Armed Services",
    "house armed services": "Armed Services",
    "senate armed services": "Armed Services",
    "energy and commerce": "Energy and Commerce",
    "house energy and commerce": "Energy and Commerce",
    "financial services": "Financial Services",
    "house financial services": "Financial Services",
    "banking, housing, and urban affairs": "Banking, Housing, and Urban Affairs",
    "senate banking": "Banking, Housing, and Urban Affairs",
    "intelligence": "Intelligence",
    "house intelligence": "Intelligence",
    "senate intelligence": "Intelligence",
    "permanent select committee on intelligence": "Intelligence",
    "foreign affairs": "Foreign Affairs",
    "house foreign affairs": "Foreign Affairs",
    "homeland security": "Homeland Security",
    "house homeland security": "Homeland Security",
    "agriculture": "Agriculture",
    "house agriculture": "Agriculture",
    "senate agriculture": "Agriculture",
    "transportation and infrastructure": "Transportation and Infrastructure",
    "house transportation and infrastructure": "Transportation and Infrastructure",
}

# Verified Congressional member committee assignments
POLITICIAN_ROSTER: Mapping[str, tuple[str, ...]] = {
    "Tommy Tuberville": (
        "Armed Services",
        "Agriculture",
    ),
    "Dan Crenshaw": ("Energy and Commerce",),
    "Michael McCaul": (
        "Foreign Affairs",
        "Homeland Security",
    ),
    "Ro Khanna": ("Armed Services",),
    "Josh Gottheimer": (
        "Financial Services",
        "Intelligence",
    ),
    "Markwayne Mullin": ("Armed Services",),
}


def derive_trade_direction(
    transaction_type: TransactionType,
    instrument: InstrumentType,
) -> TradeDirection:
    """Derive true economic exposure from transaction type and instrument.

    Purchasing puts or selling calls/stock is bearish.
    Purchasing stock/calls or selling puts is bullish.
    """
    if instrument in ("stock", "call_option"):
        return "bullish" if transaction_type == "purchase" else "bearish"
    if instrument == "put_option":
        return "bearish" if transaction_type == "purchase" else "bullish"
    return "neutral"


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
    instrument: InstrumentType = "stock"
    committees: tuple[str, ...] = ()
    asset_description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "ticker", self.ticker.upper().strip())
        if not self.committees:
            default_committees = POLITICIAN_ROSTER.get(self.politician, ())
            object.__setattr__(self, "committees", default_committees)

    @property
    def direction(self) -> TradeDirection:
        return derive_trade_direction(self.transaction_type, self.instrument)


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
    direction: TradeDirection
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
    as_of_date_str: str | None = None,
    half_life_days: float = 30.0,
) -> float:
    """Compute exponential decay factor reflecting informational shelf-life.

    Considers both statutory disclosure delay and post-disclosure aging at
    the specified analysis date (defaults to disclosure date if omitted).
    """
    if half_life_days <= 0:
        return 0.0

    try:
        t_date = date.fromisoformat(trade_date_str)
        ref_str = as_of_date_str if as_of_date_str else disclosure_date_str
        ref_date = date.fromisoformat(ref_str)
        elapsed_days = max(0, (ref_date - t_date).days)
    except (ValueError, TypeError):
        elapsed_days = 30

    decay = math.pow(0.5, elapsed_days / half_life_days)
    return round(max(0.05, min(1.0, decay)), 4)


def evaluate_committee_conflict(trade: PoliticianTrade) -> tuple[float, tuple[str, ...]]:
    """Determine whether politician's committee assignments overlap with ticker jurisdiction."""
    matched_committees: list[str] = []
    symbol = trade.ticker

    for comm in trade.committees:
        cleaned = comm.strip().lower()
        if not cleaned:
            continue

        canonical_name = COMMITTEE_ALIASES.get(cleaned)
        if not canonical_name:
            for alias_key, canon in COMMITTEE_ALIASES.items():
                if alias_key == cleaned or (len(cleaned) >= 5 and alias_key in cleaned):
                    canonical_name = canon
                    break

        if canonical_name and canonical_name in COMMITTEE_JURISDICTIONS:
            tickers = COMMITTEE_JURISDICTIONS[canonical_name]
            if symbol in tickers:
                matched_committees.append(canonical_name)

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
    as_of_date: str | None = None,
) -> CongressionalAlphaSignal:
    """Synthesize Congressional insider conflict, disclosure decay, and options flow."""
    conflict_score, matches = evaluate_committee_conflict(trade)
    decay = calculate_disclosure_decay(
        trade.trade_date,
        trade.disclosure_date,
        as_of_date_str=as_of_date,
    )
    direction = trade.direction

    # Base confidence: product of conflict relevance and disclosure freshness
    base_confidence = conflict_score * decay

    flow_confirmed = False
    flow_meta: dict[str, Any] | None = None
    flow_multiplier = 1.0

    if flow and flow.ticker == trade.ticker:
        # Flow alignment check: call flow confirms bullish; put flow confirms bearish
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

        if (direction == "bullish" and is_bullish_flow) or (
            direction == "bearish" and is_bearish_flow
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

    # Decision Matrix based on verified economic direction
    action: TradeAction
    if composite >= 0.50 and direction != "neutral":
        if direction == "bullish":
            if gex_regime == "positive_gamma":
                action = "SELL_PUT_CREDIT"
            else:
                action = "BUY_CALL_SPREAD"
        else:
            action = "BUY_PUT_SPREAD"
    else:
        action = "NEUTRAL_HOLD"

    rationale_parts = [
        f"Politician {trade.politician} ({trade.party}-{trade.chamber.upper()}) "
        f"{trade.transaction_type.upper()} {trade.instrument.upper()} on {trade.ticker} "
        f"(Direction: {direction.upper()}).",
        f"Conflict score: {conflict_score:.2f} (Jurisdiction: {', '.join(matches) if matches else 'None'}).",
        f"Disclosure decay: {decay:.2f}.",
    ]
    if flow_confirmed and flow:
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
        direction=direction,
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
