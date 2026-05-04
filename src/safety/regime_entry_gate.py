"""Entry gating for live market-regime snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RegimeEntryDecision:
    """Decision produced by the regime entry gate."""

    allowed: bool
    reason: str
    level: str


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def evaluate_regime_entry(
    snapshot: Any,
    *,
    min_confidence: float = 0.30,
    max_normal_vix: float = 25.0,
) -> RegimeEntryDecision:
    """Return whether an iron-condor entry may proceed for a regime snapshot.

    Unknown regimes must fail closed. Known calm/trending regimes with a normal
    VIX may continue to downstream gates even when model confidence is low; that
    avoids treating a calibrated calm signal as equivalent to missing data.
    """
    regime_id = int(_as_float(getattr(snapshot, "regime_id", -1), -1.0))
    label = str(getattr(snapshot, "label", "unknown") or "unknown")
    confidence = _as_float(getattr(snapshot, "confidence", 0.0), 0.0)
    vix_level = _as_float(getattr(snapshot, "vix_level", 0.0), 0.0)

    if regime_id < 0:
        return RegimeEntryDecision(
            allowed=False,
            level="block",
            reason=(
                "REGIME BLOCKED: unknown regime "
                f"(id={regime_id}, conf={confidence:.2f}). Fail-closed."
            ),
        )

    if regime_id >= 2:
        return RegimeEntryDecision(
            allowed=False,
            level="block",
            reason=(
                f"REGIME BLOCKED: {label} regime (id={regime_id}). "
                "Iron condors require calm/low-trend markets."
            ),
        )

    transition = getattr(snapshot, "transition_prediction", None)
    if transition is not None:
        predicted = str(getattr(transition, "predicted_regime", "") or "").lower()
        transition_detected = bool(getattr(transition, "transition_detected", False))
        if transition_detected and predicted in {"volatile", "spike"}:
            probability = _as_float(getattr(transition, "transition_probability", 0.0), 0.0)
            return RegimeEntryDecision(
                allowed=False,
                level="block",
                reason=(
                    f"REGIME TRANSITION: {predicted} predicted "
                    f"(prob={probability:.2f}). Blocking entry."
                ),
            )

    if confidence < min_confidence:
        if 0 < vix_level < max_normal_vix:
            return RegimeEntryDecision(
                allowed=True,
                level="warn",
                reason=(
                    f"REGIME LOW CONFIDENCE ALLOWED: {label} "
                    f"(id={regime_id}, conf={confidence:.2f}, VIX={vix_level:.1f}). "
                    "Proceeding to downstream gates because VIX is normal."
                ),
            )
        return RegimeEntryDecision(
            allowed=False,
            level="block",
            reason=(
                "REGIME BLOCKED: low-confidence regime without normal VIX confirmation "
                f"(id={regime_id}, conf={confidence:.2f}, VIX={vix_level:.1f})."
            ),
        )

    return RegimeEntryDecision(
        allowed=True,
        level="pass",
        reason=(
            f"REGIME PASS: {label} (id={regime_id}, conf={confidence:.2f}, VIX={vix_level:.1f})."
        ),
    )
