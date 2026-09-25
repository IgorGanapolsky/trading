"""Tests for multi-venue consensus pricing and cross-exchange dispersion oracle."""

from __future__ import annotations

import pytest
from src.analytics.venue_consensus_oracle import (
    VenueQuote,
    calculate_venue_consensus,
    compute_dispersion_bps,
    generate_canonical_receipt,
)


def test_compute_dispersion_bps():
    # 500.0 vs 500.5 at price 500.0 -> (0.5 / 500) * 10000 = 10 bps
    prices = [500.0, 500.25, 500.5]
    disp = compute_dispersion_bps(prices, 500.0)
    assert disp == pytest.approx(10.0, abs=0.01)


def test_insufficient_coverage():
    quotes = [
        VenueQuote(venue="CBOE", price=500.0),
        VenueQuote(venue="ARCA", price=500.1),
    ]
    res = calculate_venue_consensus("SPY", quotes, min_sources=3)
    assert res.grade == "insufficient-coverage"
    assert res.is_safe_to_execute is False
    assert res.rejection_reason is not None
    assert "Insufficient reporting venues" in res.rejection_reason


def test_consensus_agreement():
    quotes = [
        VenueQuote(venue="CBOE", price=500.0),
        VenueQuote(venue="ARCA", price=500.02),
        VenueQuote(venue="PHLX", price=500.01),
        VenueQuote(venue="BATS", price=500.03),
    ]
    res = calculate_venue_consensus("SPY", quotes, min_sources=3, max_dispersion_bps=15.0)
    assert res.grade == "consensus"
    assert res.is_safe_to_execute is True
    assert res.dispersion_bps < 15.0
    assert res.sources_count == 4
    assert res.receipt_hash is not None


def test_venue_disagreement_detection():
    # Severe cross-exchange divergence (e.g. flash spike on one exchange)
    quotes = [
        VenueQuote(venue="CBOE", price=500.0),
        VenueQuote(venue="ARCA", price=502.5),
        VenueQuote(venue="PHLX", price=501.2),
    ]
    # Spread of 2.5 on 501.2 -> ~50 bps (> 15 bps max)
    res = calculate_venue_consensus("SPY", quotes, min_sources=3, max_dispersion_bps=15.0)
    assert res.grade == "venue-disagreement"
    assert res.is_safe_to_execute is False
    assert "exceeds limit" in (res.rejection_reason or "")


def test_outlier_filtering():
    quotes = [
        VenueQuote(venue="CBOE", price=500.0),
        VenueQuote(venue="ARCA", price=500.01),
        VenueQuote(venue="PHLX", price=500.02),
        VenueQuote(venue="BATS", price=500.01),
        VenueQuote(venue="MALFUNCTION_VENUE", price=550.0),  # Extreme outlier
    ]
    res = calculate_venue_consensus("SPY", quotes, min_sources=3, outlier_std_devs=2.0)
    assert res.grade == "blended"
    assert res.is_safe_to_execute is True
    assert res.sources_count == 4  # 1 venue was trimmed


def test_canonical_receipt_deterministic():
    hash1 = generate_canonical_receipt("BTC", 84000.0, "2026-09-25T17:00:00Z", "consensus", 30, 4.5)
    hash2 = generate_canonical_receipt("BTC", 84000.0, "2026-09-25T17:00:00Z", "consensus", 30, 4.5)
    assert hash1 == hash2
    assert len(hash1) == 64
