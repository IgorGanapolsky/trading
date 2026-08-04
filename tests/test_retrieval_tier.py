"""Tests for retrieval-tier reporting.

The point of this module is that a degraded retrieval stack must never be invisible.
These tests assert the *labelling* is honest, because the original bug was not a crash
-- it was a correct-looking number attached to the wrong configuration.
"""

from __future__ import annotations

import importlib.util

import pytest

from src.rag import retrieval_tier


@pytest.fixture
def hide(monkeypatch):
    """Make chosen modules look absent to the tier reporter."""

    def _hide(*names: str):
        original = importlib.util.find_spec

        def fake(name, *args, **kwargs):
            if name in names:
                return None
            return original(name, *args, **kwargs)

        monkeypatch.setattr(importlib.util, "find_spec", fake)

    return _hide


def test_missing_cross_encoder_marks_quality_degraded(hide) -> None:
    hide("sentence_transformers")
    tier = retrieval_tier.describe_retrieval_tier()

    assert tier["quality_degraded"] is True
    assert tier["embedder"] == "tfidf-fallback"
    assert tier["reranker"] == "heuristic"
    assert "0.2" in retrieval_tier.tier_summary_line()


def test_absent_unmeasured_dep_does_not_claim_quality_loss(hide) -> None:
    """Regression on my own bug: lancedb absence must not be reported as degraded.

    Both measured rows were taken with lancedb absent, so blaming it for the
    precision gap would attach a real number to a configuration it never described.
    """
    hide("lancedb")
    tier = retrieval_tier.describe_retrieval_tier()

    assert tier["quality_degraded"] is False, "lancedb has no measured effect on the gate"
    assert "lancedb" in tier["unmeasured_absent"]

    summary = retrieval_tier.tier_summary_line()
    assert summary.startswith("retrieval tier FULL")
    assert "no measured effect" in summary
    assert "0.2 vs 0.36" not in summary, "must not quote a delta lancedb was never measured on"


def test_full_tier_reports_real_components() -> None:
    tier = retrieval_tier.describe_retrieval_tier()
    if tier["quality_degraded"]:
        pytest.skip("cross-encoder not installed in this environment")

    assert tier["embedder"] == "BAAI/bge-base-en-v1.5"
    assert tier["reranker"] == "cross-encoder"
    assert retrieval_tier.tier_summary_line().startswith("retrieval tier FULL")


def test_measured_numbers_are_labelled_by_configuration() -> None:
    """The constants must name the config they were measured in, not a vague 'tier'."""
    assert retrieval_tier.MEASURED_WITH_CROSS_ENCODER["precision_at_5"] == 0.36
    assert retrieval_tier.MEASURED_WITHOUT_CROSS_ENCODER["precision_at_5"] == 0.20
    assert (
        retrieval_tier.MEASURED_WITH_CROSS_ENCODER["precision_at_5"]
        > retrieval_tier.MEASURED_WITHOUT_CROSS_ENCODER["precision_at_5"]
    )
