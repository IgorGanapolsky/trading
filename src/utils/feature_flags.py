"""Canonical feature flags for dormant non-SPY strategy surfaces."""

from __future__ import annotations

import os


def _env_flag(name: str, *, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def prediction_enabled() -> bool:
    """Prediction markets were removed in Dec 2025 and stay disabled."""
    return False


def reit_enabled() -> bool:
    """REIT trading must stay opt-in when explicitly enabled."""
    return _env_flag("ENABLE_REIT_STRATEGY", default=False)


def precious_metals_enabled() -> bool:
    """Precious-metals trading must stay opt-in when explicitly enabled."""
    return _env_flag("ENABLE_PRECIOUS_METALS", default=False)


__all__ = ["prediction_enabled", "reit_enabled", "precious_metals_enabled"]
