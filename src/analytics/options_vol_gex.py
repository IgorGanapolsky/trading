"""Options Volatility, Gamma Exposure (GEX), and Market Tide Analytics.

Implements quant signal and risk rail formulations:
1. Dealer Gamma Exposure (GEX), Call Wall, Put Wall, Gamma Magnet, and Zero-Gamma Flip.
2. Expiration Max Pain level (dealer cash-loss minimization pin).
3. Term Structure Backwardation slope and IV/RV Richness ratio.
4. Market Tide Net Premium and Ask-Side Flow Aggressiveness (>70% threshold).

100% in-house calculation from free Alpaca options chains and local data (Zero paid API cost).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence


@dataclass(frozen=True)
class GEXLevelResult:
    """Quantitative summary of dealer gamma exposure across the strike matrix."""

    spot_price: float
    net_gamma: float
    gamma_regime: Literal["positive_gamma", "negative_gamma"]
    call_wall: float | None
    put_wall: float | None
    gamma_magnet: float | None
    gamma_flip: float | None
    nearby_flips: tuple[float, ...]
    per_strike_gex: Mapping[float, float]


@dataclass(frozen=True)
class TermStructureResult:
    """Term structure slope and volatility risk premium metrics."""

    front_dte: float
    front_iv: float
    back_dte: float
    back_iv: float
    slope: float
    is_backwardated: bool
    iv_rv_ratio: float
    is_rich: bool
    credit_spread_favorable: bool


@dataclass(frozen=True)
class MarketTideResult:
    """Aggregated intraday options flow sentiment and order aggressiveness."""

    net_call_premium: float
    net_put_premium: float
    market_tide_delta: float
    sentiment: Literal["bullish", "bearish", "neutral"]
    total_ask_volume: int
    total_bid_volume: int
    ask_side_ratio: float
    aggressive_buying_detected: bool


@dataclass(frozen=True)
class HedgingFlowResult:
    """Estimated dealer delta-hedging rebalancing flow for a given price move.

    Formula (Unusual Whales Periscope delta-hedging attribution):
        Hedging Flow = - Net Gamma * Spot * (Spot * spot_move_pct) * 100
    In positive gamma, dealers buy weakness and sell strength (stabilizing dampener).
    In negative gamma, dealers sell weakness and buy strength (cascading accelerator).
    """

    spot_price: float
    net_gamma: float
    spot_move_pct: float
    hedging_shares: float
    hedging_flow_dollars: float
    hedging_pressure: Literal["supportive_buying", "accelerating_selling", "neutral"]
    description: str


@dataclass(frozen=True)
class DealerDefenseResult:
    """Evaluation of whether key market maker support/resistance walls are defended or abandoned."""

    spot_price: float
    put_wall: float | None
    put_wall_status: Literal["defended", "abandoned", "unknown"]
    call_wall: float | None
    call_wall_status: Literal["defended", "abandoned", "unknown"]
    gamma_flip: float | None
    above_gamma_flip: bool | None
    regime_safety: Literal["safe_positive_gamma", "hazardous_negative_gamma", "unhedged_breakdown"]
    summary: str


@dataclass(frozen=True)
class RiskPocketResult:
    """0DTE / short-dated option dealer risk pocket near spot."""

    strike: float
    distance_pct: float
    zero_dte_oi: int
    total_oi: int
    oi_concentration_pct: float
    risk_level: Literal["critical", "elevated", "normal"]
    hazard_description: str


def black_scholes_gamma(
    spot: float,
    strike: float,
    time_to_expiry_years: float,
    iv: float,
    risk_free_rate: float = 0.045,
    dividend_yield: float = 0.013,
) -> float:
    """Calculate Black-Scholes option gamma for a European option.

    Gamma is identical for both calls and puts:
        d1 = [ln(S/K) + (r - q + sigma^2 / 2) * T] / (sigma * sqrt(T))
        Gamma = exp(-q * T) * phi(d1) / (S * sigma * sqrt(T))
    """
    if spot <= 0.0 or strike <= 0.0 or time_to_expiry_years <= 0.0 or iv <= 0.0:
        return 0.0

    sqrt_t = math.sqrt(time_to_expiry_years)
    denom = iv * sqrt_t
    if denom <= 0.0:
        return 0.0

    d1 = (
        math.log(spot / strike)
        + (risk_free_rate - dividend_yield + 0.5 * iv * iv) * time_to_expiry_years
    ) / denom

    phi_d1 = (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * d1 * d1)
    gamma = math.exp(-dividend_yield * time_to_expiry_years) * phi_d1 / (spot * denom)
    return gamma


def calculate_gex_levels(
    spot_price: float,
    strikes: Sequence[float],
    call_gammas: Sequence[float],
    put_gammas: Sequence[float],
    call_ois: Sequence[int],
    put_ois: Sequence[int],
) -> GEXLevelResult:
    """Calculate aggregate and per-strike GEX, Call/Put Walls, Magnet, and Flip.

    Dealer convention:
    - Dealers short call options to retail buyers: Calls contribute positive gamma to dealers.
    - Dealers long put options or retail buying puts: Puts contribute negative gamma to dealers.
    - Net GEX per strike = SpotGEX(Call) + SpotGEX(Put), where SpotGEX(Put) is negative.
    - Spot GEX = Gamma * OI * Spot^2 * 100 (in dollar gamma terms per 1% or 1-point move).
    """
    if not (len(strikes) == len(call_gammas) == len(put_gammas) == len(call_ois) == len(put_ois)):
        raise ValueError("All strike, gamma, and open interest sequences must have equal length.")

    if not strikes or spot_price <= 0.0:
        return GEXLevelResult(
            spot_price=spot_price,
            net_gamma=0.0,
            gamma_regime="positive_gamma",
            call_wall=None,
            put_wall=None,
            gamma_magnet=None,
            gamma_flip=None,
            nearby_flips=(),
            per_strike_gex={},
        )

    # Sort strikes ascending
    sorted_indices = sorted(range(len(strikes)), key=lambda i: strikes[i])
    sorted_strikes = [strikes[i] for i in sorted_indices]

    per_strike_gex: dict[float, float] = {}
    multiplier = spot_price * spot_price * 100.0

    for idx in sorted_indices:
        k = strikes[idx]
        call_gex = call_gammas[idx] * call_ois[idx] * multiplier
        put_gex = -1.0 * put_gammas[idx] * put_ois[idx] * multiplier
        per_strike_gex[k] = call_gex + put_gex

    net_gamma = sum(per_strike_gex.values())
    gamma_regime: Literal["positive_gamma", "negative_gamma"] = (
        "positive_gamma" if net_gamma >= 0.0 else "negative_gamma"
    )

    # Call Wall: strike above spot with largest positive net gamma (resistance)
    call_candidates = [(k, gex) for k, gex in per_strike_gex.items() if k > spot_price and gex > 0]
    call_wall = max(call_candidates, key=lambda item: item[1])[0] if call_candidates else None

    # Put Wall: strike below spot with largest positive net gamma / strongest put support
    put_candidates = [(k, gex) for k, gex in per_strike_gex.items() if k < spot_price and gex > 0]
    put_wall = max(put_candidates, key=lambda item: item[1])[0] if put_candidates else None

    # Gamma Magnet: strike with largest-magnitude net gamma (strongest pin)
    gamma_magnet = (
        max(per_strike_gex.items(), key=lambda item: abs(item[1]))[0] if per_strike_gex else None
    )

    # Gamma Flip crossings: find zero crossings between adjacent strikes
    flips: list[float] = []
    for i in range(len(sorted_strikes) - 1):
        k1 = sorted_strikes[i]
        k2 = sorted_strikes[i + 1]
        g1 = per_strike_gex[k1]
        g2 = per_strike_gex[k2]

        if (g1 <= 0.0 and g2 > 0.0) or (g1 >= 0.0 and g2 < 0.0):
            if abs(g2 - g1) > 1e-9:
                flip_price = k1 + (0.0 - g1) / (g2 - g1) * (k2 - k1)
                flips.append(round(flip_price, 2))

    # Order flips by distance to spot, capped at 5
    flips.sort(key=lambda price: abs(price - spot_price))
    nearby_flips = tuple(flips[:5])
    gamma_flip = nearby_flips[0] if nearby_flips else None

    return GEXLevelResult(
        spot_price=spot_price,
        net_gamma=net_gamma,
        gamma_regime=gamma_regime,
        call_wall=call_wall,
        put_wall=put_wall,
        gamma_magnet=gamma_magnet,
        gamma_flip=gamma_flip,
        nearby_flips=nearby_flips,
        per_strike_gex=per_strike_gex,
    )


def calculate_max_pain(
    strikes: Sequence[float],
    call_ois: Sequence[int],
    put_ois: Sequence[int],
) -> float:
    """Calculate Max Pain strike where option buyers lose the most money at expiration.

    For each candidate expiration price K_eval in strikes:
        Total Cash Loss = Sum_j [Call_OI_j * max(0, K_eval - K_j) * 100]
                        + Sum_j [Put_OI_j * max(0, K_j - K_eval) * 100]
    Max Pain is the strike that minimizes Total Cash Loss (minimizes dealer payout).
    """
    if not (len(strikes) == len(call_ois) == len(put_ois)):
        raise ValueError("Strikes and Open Interest sequences must be of equal length.")

    if not strikes:
        return 0.0

    min_loss = float("inf")
    max_pain_strike = strikes[0]

    for k_eval in strikes:
        loss = 0.0
        for idx, k in enumerate(strikes):
            call_payoff = max(0.0, k_eval - k) * call_ois[idx] * 100.0
            put_payoff = max(0.0, k - k_eval) * put_ois[idx] * 100.0
            loss += call_payoff + put_payoff

        if loss < min_loss:
            min_loss = loss
            max_pain_strike = k_eval

    return max_pain_strike


def calculate_iv_term_structure(
    front_dte: float,
    front_iv: float,
    back_dte: float,
    back_iv: float,
    rv30: float = 0.0,
) -> TermStructureResult:
    """Calculate term structure slope and determine if IV backwardation exists.

    Backwardation filter from Unusual Whales:
    - Linear slope <= -0.00406 per day indicates front-month IV is sharply inverted.
    - Richness ratio IV30 / RV30 >= 1.25 indicates front IV is expensive vs realized volatility.
    - Both conditions together signal optimal regime for front credit spread harvest.
    """
    delta_dte = back_dte - front_dte
    if abs(delta_dte) < 1e-6:
        slope = 0.0
    else:
        slope = (back_iv - front_iv) / delta_dte

    # UW backwardation gating threshold: slope <= -0.00406
    is_backwardated = slope <= -0.00406

    iv_rv_ratio = (front_iv / rv30) if rv30 > 0.0 else 1.0
    is_rich = iv_rv_ratio >= 1.25

    credit_spread_favorable = is_backwardated and is_rich

    return TermStructureResult(
        front_dte=front_dte,
        front_iv=front_iv,
        back_dte=back_dte,
        back_iv=back_iv,
        slope=slope,
        is_backwardated=is_backwardated,
        iv_rv_ratio=iv_rv_ratio,
        is_rich=is_rich,
        credit_spread_favorable=credit_spread_favorable,
    )


def calculate_market_tide(
    trades: Sequence[Mapping[str, Any]],
) -> MarketTideResult:
    """Calculate Net Option Premium Flow (Market Tide) and Ask-Side flow intensity.

    Rules:
    - Calls bought at the ask increase Net Call Premium (+).
    - Calls sold at the bid decrease Net Call Premium (-).
    - Puts bought at the ask increase Net Put Premium (+).
    - Puts sold at the bid decrease Net Put Premium (-).
    - Market Tide Delta = Net Call Premium - Net Put Premium.
    - Ask-Side Ratio = Total Ask Volume / (Total Ask Volume + Total Bid Volume).
    - Aggressive Buying Detected when Ask-Side Ratio >= 0.70.
    """
    net_call_premium = 0.0
    net_put_premium = 0.0
    total_ask_volume = 0
    total_bid_volume = 0

    for trade in trades:
        side = str(trade.get("side", "")).strip().lower()
        option_type = str(trade.get("type", "")).strip().lower()
        premium = float(trade.get("premium", 0.0))
        volume = int(trade.get("volume", 0))

        if side == "ask":
            total_ask_volume += volume
            if option_type == "call":
                net_call_premium += premium
            elif option_type == "put":
                net_put_premium += premium
        elif side == "bid":
            total_bid_volume += volume
            if option_type == "call":
                net_call_premium -= premium
            elif option_type == "put":
                net_put_premium -= premium

    market_tide_delta = net_call_premium - net_put_premium

    if market_tide_delta > 1000.0:
        sentiment: Literal["bullish", "bearish", "neutral"] = "bullish"
    elif market_tide_delta < -1000.0:
        sentiment = "bearish"
    else:
        sentiment = "neutral"

    total_volume = total_ask_volume + total_bid_volume
    ask_side_ratio = (total_ask_volume / total_volume) if total_volume > 0 else 0.0
    aggressive_buying_detected = ask_side_ratio >= 0.70

    return MarketTideResult(
        net_call_premium=net_call_premium,
        net_put_premium=net_put_premium,
        market_tide_delta=market_tide_delta,
        sentiment=sentiment,
        total_ask_volume=total_ask_volume,
        total_bid_volume=total_bid_volume,
        ask_side_ratio=ask_side_ratio,
        aggressive_buying_detected=aggressive_buying_detected,
    )


def calculate_expected_hedging_flow(
    spot_price: float,
    net_gamma: float,
    spot_move_pct: float = -0.01,
) -> HedgingFlowResult:
    """Calculate expected dealer delta-hedging rebalancing flow for a given spot move.

    Replicates Unusual Whales Periscope 'Where delta-hedging flows may push market next'.
    """
    if spot_price <= 0.0:
        return HedgingFlowResult(
            spot_price=spot_price,
            net_gamma=net_gamma,
            spot_move_pct=spot_move_pct,
            hedging_shares=0.0,
            hedging_flow_dollars=0.0,
            hedging_pressure="neutral",
            description="Invalid spot price",
        )

    delta_s = spot_price * spot_move_pct
    hedging_shares = -1.0 * net_gamma * delta_s * 100.0
    hedging_flow_dollars = hedging_shares * (spot_price + delta_s)

    if net_gamma > 1e-6:
        if spot_move_pct < 0:
            pressure: Literal["supportive_buying", "accelerating_selling", "neutral"] = (
                "supportive_buying"
            )
            desc = "Dealers long gamma: mechanical rebalancing provides supportive dip buying."
        else:
            pressure = "supportive_buying"
            desc = "Dealers long gamma: mechanical rebalancing trims rally into resistance."
    elif net_gamma < -1e-6:
        if spot_move_pct < 0:
            pressure = "accelerating_selling"
            desc = "Dealers short gamma: mechanical rebalancing triggers cascading selling into weakness."
        else:
            pressure = "accelerating_selling"
            desc = "Dealers short gamma: mechanical rebalancing fuels upside short squeezes."
    else:
        pressure = "neutral"
        desc = "Dealers delta-neutral at zero gamma: minimal mechanical flow pressure."

    return HedgingFlowResult(
        spot_price=spot_price,
        net_gamma=net_gamma,
        spot_move_pct=spot_move_pct,
        hedging_shares=round(hedging_shares, 2),
        hedging_flow_dollars=round(hedging_flow_dollars, 2),
        hedging_pressure=pressure,
        description=desc,
    )


def evaluate_dealer_defense_levels(
    spot_price: float,
    put_wall: float | None,
    call_wall: float | None,
    gamma_flip: float | None,
) -> DealerDefenseResult:
    """Evaluate whether dealer support/resistance walls are defended or abandoned.

    Replicates Unusual Whales Periscope 'Which price levels they are defending or abandoning'.
    """
    if spot_price <= 0.0:
        return DealerDefenseResult(
            spot_price=spot_price,
            put_wall=put_wall,
            put_wall_status="unknown",
            call_wall=call_wall,
            call_wall_status="unknown",
            gamma_flip=gamma_flip,
            above_gamma_flip=None,
            regime_safety="hazardous_negative_gamma",
            summary="Invalid spot price",
        )

    # Put wall analysis
    if put_wall is None:
        put_status: Literal["defended", "abandoned", "unknown"] = "unknown"
    elif spot_price >= put_wall:
        put_status = "defended"
    else:
        put_status = "abandoned"

    # Call wall analysis
    if call_wall is None:
        call_status: Literal["defended", "abandoned", "unknown"] = "unknown"
    elif spot_price <= call_wall:
        call_status = "defended"
    else:
        call_status = "abandoned"

    # Gamma flip analysis
    above_flip = (spot_price >= gamma_flip) if gamma_flip is not None else None

    if put_status == "abandoned":
        safety: Literal["safe_positive_gamma", "hazardous_negative_gamma", "unhedged_breakdown"] = (
            "unhedged_breakdown"
        )
        summary = f"Put Wall at {put_wall} breached! Dealers abandoned support floor; short puts trigger forced selling."
    elif above_flip is False:
        safety = "hazardous_negative_gamma"
        summary = f"Spot below Gamma Flip ({gamma_flip}). Dealers short gamma; volatility expansion and air pockets active."
    else:
        safety = "safe_positive_gamma"
        summary = f"Spot above Put Wall ({put_wall}) and Gamma Flip ({gamma_flip}). Dealers defending support; dampening active."

    return DealerDefenseResult(
        spot_price=spot_price,
        put_wall=put_wall,
        put_wall_status=put_status,
        call_wall=call_wall,
        call_wall_status=call_status,
        gamma_flip=gamma_flip,
        above_gamma_flip=above_flip,
        regime_safety=safety,
        summary=summary,
    )


def detect_zero_dte_risk_pockets(
    spot_price: float,
    strikes: Sequence[float],
    zero_dte_put_ois: Sequence[int],
    zero_dte_call_ois: Sequence[int],
    total_put_ois: Sequence[int],
    total_call_ois: Sequence[int],
    threshold_pct: float = 0.02,
) -> list[RiskPocketResult]:
    """Detect high-leverage 0DTE dealer risk pockets within proximity of spot.

    Replicates Unusual Whales Periscope 'Where short-dated options create real risk pockets'.
    """
    if not (
        len(strikes)
        == len(zero_dte_put_ois)
        == len(zero_dte_call_ois)
        == len(total_put_ois)
        == len(total_call_ois)
    ):
        raise ValueError("All strike, 0DTE OI, and total OI sequences must have equal length.")

    if spot_price <= 0.0 or not strikes:
        return []

    pockets: list[RiskPocketResult] = []

    for idx, k in enumerate(strikes):
        dist_pct = abs(k - spot_price) / spot_price
        if dist_pct > threshold_pct:
            continue

        z_oi = zero_dte_put_ois[idx] + zero_dte_call_ois[idx]
        t_oi = total_put_ois[idx] + total_call_ois[idx]
        conc = (z_oi / t_oi) if t_oi > 0 else 0.0

        if conc >= 0.35 or z_oi >= 5000:
            risk: Literal["critical", "elevated", "normal"] = "critical"
            hazard = f"Severe 0DTE concentration ({conc * 100:.1f}%) at strike {k}. High dealer rebalancing velocity."
        elif conc >= 0.20 or z_oi >= 2000:
            risk = "elevated"
            hazard = f"Elevated 0DTE concentration ({conc * 100:.1f}%) at strike {k}."
        else:
            risk = "normal"
            hazard = "Normal short-dated distribution."

        pockets.append(
            RiskPocketResult(
                strike=k,
                distance_pct=round(dist_pct, 4),
                zero_dte_oi=z_oi,
                total_oi=t_oi,
                oi_concentration_pct=round(conc, 4),
                risk_level=risk,
                hazard_description=hazard,
            )
        )

    pockets.sort(key=lambda item: item.distance_pct)
    return pockets
