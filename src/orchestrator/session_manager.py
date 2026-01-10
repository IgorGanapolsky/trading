"""Session management extracted from TradingOrchestrator.

This module handles:
- Building session profiles (market day detection, ticker selection)
- Weekend mode configuration
- Session type determination
- RL threshold adjustments

Extracted Jan 10, 2026 per ArjanCodes clean architecture principles.
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timezone
from typing import Any

import holidays

logger = logging.getLogger(__name__)

_US_HOLIDAYS_CACHE: dict[int, holidays.HolidayBase] = {}


def _get_us_holidays(year: int) -> holidays.HolidayBase:
    """Get cached US holidays for a given year."""
    if year not in _US_HOLIDAYS_CACHE:
        _US_HOLIDAYS_CACHE[year] = holidays.US(years=[year])
    return _US_HOLIDAYS_CACHE[year]


def is_us_market_day(day: date | None = None) -> bool:
    """Check if the given day is a US market trading day.

    Args:
        day: Date to check. Defaults to today (UTC).

    Returns:
        True if markets are open, False if weekend or holiday.
    """
    current_day = day or datetime.now(timezone.utc).date()
    if current_day.weekday() >= 5:  # Saturday/Sunday
        return False
    calendar = _get_us_holidays(current_day.year)
    return current_day not in calendar


class SessionManager:
    """Manages trading session configuration and state.

    Responsibilities:
    - Detect market day vs weekend/holiday
    - Select appropriate tickers for session type
    - Configure RL thresholds and momentum overrides
    - Build session profiles for the orchestrator

    This class is injected into TradingOrchestrator to reduce its complexity.
    """

    def __init__(
        self,
        *,
        default_tickers: list[str],
        weekend_proxy_symbols: str | None = None,
    ) -> None:
        """Initialize session manager.

        Args:
            default_tickers: Default ticker list for market hours.
            weekend_proxy_symbols: Comma-separated weekend proxy symbols.
        """
        self.default_tickers = [t.strip().upper() for t in default_tickers if t.strip()]
        self.weekend_proxy_symbols = weekend_proxy_symbols or os.getenv(
            "WEEKEND_PROXY_SYMBOLS", "BITO,RWCR"
        )
        self._current_profile: dict[str, Any] | None = None

    @property
    def current_profile(self) -> dict[str, Any] | None:
        """Get the current session profile."""
        return self._current_profile

    def build_session_profile(self) -> dict[str, Any]:
        """Build session profile based on current date and market status.

        Returns:
            Dict containing:
            - session_type: "market_hours" or "weekend"
            - is_market_day: True if markets are open
            - tickers: List of tickers to process
            - rl_threshold: RL confidence threshold
            - momentum_overrides: Dict of momentum parameter adjustments
        """
        today = datetime.now(timezone.utc).date()
        market_day = is_us_market_day(today)

        proxy_list = [
            symbol.strip().upper()
            for symbol in self.weekend_proxy_symbols.split(",")
            if symbol.strip()
        ]

        momentum_overrides: dict[str, float] = {}

        # RELAXED THRESHOLD (Dec 4, 2025): Reduced from 0.6 to 0.45
        # Previous: 60% confidence → rejected 30-40% of candidates at Gate 2
        # New: 45% confidence → more balanced, still above random (50%)
        rl_threshold = float(os.getenv("RL_CONFIDENCE_THRESHOLD", "0.45"))
        session_type = "market_hours"

        if not market_day:
            session_type = "weekend"
            proxy_list = proxy_list or ["BITO"]
            momentum_overrides = {
                "rsi_overbought": float(os.getenv("WEEKEND_RSI_OVERBOUGHT", "65.0")),
                "macd_threshold": float(os.getenv("WEEKEND_MACD_THRESHOLD", "-0.05")),
                "volume_min": float(os.getenv("WEEKEND_VOLUME_MIN", "0.5")),
            }
            rl_threshold = float(os.getenv("RL_WEEKEND_CONFIDENCE_THRESHOLD", "0.55"))

        tickers = self.default_tickers if market_day else proxy_list

        profile = {
            "session_type": session_type,
            "is_market_day": market_day,
            "tickers": tickers,
            "rl_threshold": rl_threshold,
            "momentum_overrides": momentum_overrides,
            "date": today.isoformat(),
        }

        self._current_profile = profile
        logger.info(
            "Session profile built: type=%s, market_day=%s, tickers=%d, rl_threshold=%.2f",
            session_type,
            market_day,
            len(tickers),
            rl_threshold,
        )

        return profile

    def get_active_tickers(self) -> list[str]:
        """Get the active ticker list for the current session.

        If no profile has been built, builds one first.
        """
        if self._current_profile is None:
            self.build_session_profile()
        return self._current_profile.get("tickers", self.default_tickers)  # type: ignore

    def is_weekend_mode(self) -> bool:
        """Check if the current session is in weekend mode."""
        if self._current_profile is None:
            self.build_session_profile()
        return self._current_profile.get("session_type") == "weekend"  # type: ignore

    def get_rl_threshold(self) -> float:
        """Get the RL confidence threshold for the current session."""
        if self._current_profile is None:
            self.build_session_profile()
        return self._current_profile.get("rl_threshold", 0.45)  # type: ignore

    def maybe_reallocate_for_weekend(self, smart_dca: Any, telemetry: Any) -> None:
        """Reallocate budget for weekend sessions if enabled.

        Args:
            smart_dca: SmartDCAAllocator instance.
            telemetry: OrchestratorTelemetry instance.
        """
        if os.getenv("WEEKEND_PROXY_REALLOCATE", "true").lower() not in {"true", "1", "yes"}:
            return None

        bucket = "weekend"
        reallocated = None

        if hasattr(smart_dca, "reallocate_all_to_bucket"):
            reallocated = smart_dca.reallocate_all_to_bucket(bucket)

        if telemetry:
            telemetry.record(
                event_type="weekend.reallocate",
                payload={"bucket": bucket, "reallocated_budget": reallocated},
            )

        return None
