"""Multi-Venue Consensus Pricing & Cross-Exchange Dispersion Oracle.

Adopts institutional multi-venue consensus methodology (inspired by Pulse Verity):
1. Aggregates multi-venue quotes (CBOE, ARCA, PHLX, Binance, Coinbase).
2. Calculates cross-venue dispersion in basis points (dispersionBps).
3. Outlier rejection kernel (trimmed consensus).
4. Explicitly outputs 'venue-disagreement' grade when exchanges diverge.
5. Issues cryptographic receipt hash for execution audit trails.
"""

from __future__ import annotations

import hashlib
import statistics
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal, Sequence

ConsensusGrade = Literal[
    "consensus",
    "blended",
    "indicative",
    "venue-disagreement",
    "kernel-rejected",
    "insufficient-coverage",
]


@dataclass(frozen=True)
class VenueQuote:
    """A single price observation from an exchange venue."""

    venue: str
    price: float
    timestamp_utc: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    bid: float | None = None
    ask: float | None = None


@dataclass(frozen=True)
class VenueConsensusResult:
    """Consensus outcome across multiple venues with dispersion and cryptographic receipt."""

    symbol: str
    consensus_price: float
    grade: ConsensusGrade
    dispersion_bps: float
    interval_lower: float
    interval_upper: float
    sources_count: int
    at: str
    receipt_hash: str
    is_safe_to_execute: bool
    rejection_reason: str | None = None


def compute_dispersion_bps(prices: Sequence[float], consensus_price: float) -> float:
    """Compute the cross-exchange dispersion in basis points (bps)."""
    if not prices or consensus_price <= 0.0:
        return 0.0
    p_min = min(prices)
    p_max = max(prices)
    return round(((p_max - p_min) / consensus_price) * 10_000.0, 4)


def generate_canonical_receipt(
    symbol: str,
    price: float,
    at: str,
    grade: str,
    sources: int,
    dispersion_bps: float,
) -> str:
    """Generate SHA-256 cryptographic receipt over canonical payload."""
    canonical_text = (
        f"consensus-v1\n"
        f"symbol={symbol}\n"
        f"price={price:.6f}\n"
        f"at={at}\n"
        f"grade={grade}\n"
        f"sources={sources}\n"
        f"dispersionBps={dispersion_bps:.4f}"
    )
    return hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()


def calculate_venue_consensus(
    symbol: str,
    quotes: Sequence[VenueQuote],
    *,
    min_sources: int = 3,
    max_dispersion_bps: float = 15.0,
    outlier_std_devs: float = 2.0,
) -> VenueConsensusResult:
    """Evaluate multi-venue consensus pricing and gate execution on venue disagreement.

    Args:
        symbol: Ticker symbol (e.g. SPY, BTC, ETH).
        quotes: Sequence of VenueQuote objects from distinct venues.
        min_sources: Minimum required reporting venues for full consensus.
        max_dispersion_bps: Maximum acceptable basis point spread between venues.
        outlier_std_devs: Number of standard deviations beyond which a venue is trimmed.

    Returns:
        VenueConsensusResult with grade, dispersion, and cryptographic audit hash.
    """
    now_iso = datetime.now(UTC).isoformat()

    if not quotes:
        receipt = generate_canonical_receipt(symbol, 0.0, now_iso, "insufficient-coverage", 0, 0.0)
        return VenueConsensusResult(
            symbol=symbol,
            consensus_price=0.0,
            grade="insufficient-coverage",
            dispersion_bps=0.0,
            interval_lower=0.0,
            interval_upper=0.0,
            sources_count=0,
            at=now_iso,
            receipt_hash=receipt,
            is_safe_to_execute=False,
            rejection_reason="No quotes provided",
        )

    valid_quotes = [q for q in quotes if q.price > 0.0]
    if len(valid_quotes) < min_sources:
        p = valid_quotes[0].price if valid_quotes else 0.0
        receipt = generate_canonical_receipt(
            symbol, p, now_iso, "insufficient-coverage", len(valid_quotes), 0.0
        )
        return VenueConsensusResult(
            symbol=symbol,
            consensus_price=p,
            grade="insufficient-coverage",
            dispersion_bps=0.0,
            interval_lower=p,
            interval_upper=p,
            sources_count=len(valid_quotes),
            at=now_iso,
            receipt_hash=receipt,
            is_safe_to_execute=False,
            rejection_reason=f"Insufficient reporting venues ({len(valid_quotes)} < {min_sources})",
        )

    prices = [q.price for q in valid_quotes]
    med_p = statistics.median(prices)
    abs_deviations = [abs(p - med_p) for p in prices]
    mad = statistics.median(abs_deviations)

    # Robust outlier rejection using Median Absolute Deviation (MAD)
    # 1.4826 converts MAD to normal-consistent standard deviation estimate
    if mad > 0.0:
        threshold = outlier_std_devs * 1.4826 * mad
        filtered_prices = [p for p in prices if abs(p - med_p) <= threshold]
    else:
        # If median absolute deviation is 0, keep all prices equal to median
        filtered_prices = [p for p in prices if abs(p - med_p) == 0.0]

    if not filtered_prices:
        receipt = generate_canonical_receipt(
            symbol, med_p, now_iso, "kernel-rejected", len(prices), 0.0
        )
        return VenueConsensusResult(
            symbol=symbol,
            consensus_price=med_p,
            grade="kernel-rejected",
            dispersion_bps=0.0,
            interval_lower=min(prices),
            interval_upper=max(prices),
            sources_count=len(prices),
            at=now_iso,
            receipt_hash=receipt,
            is_safe_to_execute=False,
            rejection_reason="Kernel rejected all venues as statistical outliers",
        )

    consensus_p = round(statistics.median(filtered_prices), 6)
    lower_b = min(filtered_prices)
    upper_b = max(filtered_prices)
    dispersion = compute_dispersion_bps(filtered_prices, consensus_p)

    if dispersion > max_dispersion_bps:
        grade: ConsensusGrade = "venue-disagreement"
        safe = False
        reason = f"Cross-venue dispersion {dispersion:.2f} bps exceeds limit {max_dispersion_bps:.2f} bps"
    elif len(filtered_prices) < len(prices):
        grade = "blended"
        safe = True
        reason = None
    else:
        grade = "consensus"
        safe = True
        reason = None

    receipt = generate_canonical_receipt(
        symbol, consensus_p, now_iso, grade, len(filtered_prices), dispersion
    )

    return VenueConsensusResult(
        symbol=symbol,
        consensus_price=consensus_p,
        grade=grade,
        dispersion_bps=dispersion,
        interval_lower=lower_b,
        interval_upper=upper_b,
        sources_count=len(filtered_prices),
        at=now_iso,
        receipt_hash=receipt,
        is_safe_to_execute=safe,
        rejection_reason=reason,
    )
