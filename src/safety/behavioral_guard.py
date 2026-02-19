"""Behavioral Guard - Blocks emotion-driven trading mistakes.

Checks:
1. FOMO: Reject IC entries when SPY moved >2% intraday (premiums inflated).
2. Stop-loss cooling: 24h wait after stop-loss exit before re-entering same expiry.
3. Blacklist: Belt+suspenders check against TargetSymbols.BLACKLIST.

Fails open (allows trade) if market data is unavailable — other gates still protect.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_STATE_FILE = Path("data/behavioral_guard_state.json")
_PRUNE_HOURS = 48


@dataclass
class BehavioralCheckResult:
    """Result of behavioral guard evaluation."""

    passed: bool
    checks_run: list[str] = field(default_factory=list)
    rejections: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class BehavioralGuard:
    """Blocks emotion-driven trading mistakes."""

    def __init__(
        self,
        fomo_threshold: float | None = None,
        cooling_hours: int | None = None,
    ):
        from src.core.trading_constants import (
            FOMO_INTRADAY_MOVE_PCT,
            STOP_LOSS_COOLING_HOURS,
        )

        self.fomo_threshold = fomo_threshold if fomo_threshold is not None else FOMO_INTRADAY_MOVE_PCT
        self.cooling_hours = cooling_hours if cooling_hours is not None else STOP_LOSS_COOLING_HOURS

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        symbol: str,
        strategy_type: str | None = None,
        expiry: str | None = None,
        spy_open: float | None = None,
        spy_current: float | None = None,
    ) -> BehavioralCheckResult:
        """Run all behavioral checks.

        Args:
            symbol: Underlying or OCC symbol.
            strategy_type: e.g. "iron_condor".
            expiry: Expiry date string (YYYY-MM-DD or YYMMDD).
            spy_open: SPY open price today (for FOMO check).
            spy_current: SPY current price (for FOMO check).

        Returns:
            BehavioralCheckResult with pass/fail and details.
        """
        checks_run: list[str] = []
        rejections: list[str] = []
        warnings: list[str] = []

        # --- Blacklist ---
        checks_run.append("blacklist")
        bl_reject = self._check_blacklist(symbol)
        if bl_reject:
            rejections.append(bl_reject)

        # --- FOMO ---
        checks_run.append("fomo")
        fomo_reject = self._check_fomo(spy_open, spy_current)
        if fomo_reject:
            rejections.append(fomo_reject)

        # --- Stop-loss cooling ---
        checks_run.append("stop_loss_cooling")
        cool_reject = self._check_cooling(expiry)
        if cool_reject:
            rejections.append(cool_reject)

        passed = len(rejections) == 0
        return BehavioralCheckResult(
            passed=passed,
            checks_run=checks_run,
            rejections=rejections,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_blacklist(self, symbol: str) -> str | None:
        """Belt+suspenders blacklist check."""
        try:
            from src.constants.trading_thresholds import TargetSymbols

            blacklist = TargetSymbols.BLACKLIST
        except ImportError:
            blacklist = ["SOFI", "F", "PLTR", "T", "INTC"]

        underlying = self._extract_underlying(symbol)
        if underlying in blacklist:
            return f"BLACKLISTED: {underlying} is on the blacklist"
        return None

    def _check_fomo(
        self,
        spy_open: float | None,
        spy_current: float | None,
    ) -> str | None:
        """Reject if SPY moved >threshold intraday. Fails open if no data."""
        if spy_open is None or spy_current is None:
            return None  # Fail open
        if spy_open <= 0:
            return None
        move_pct = abs(spy_current - spy_open) / spy_open
        if move_pct >= self.fomo_threshold:
            return (
                f"FOMO: SPY moved {move_pct:.2%} intraday "
                f"(threshold {self.fomo_threshold:.2%}). Premiums inflated — wait."
            )
        return None

    def _check_cooling(self, expiry: str | None) -> str | None:
        """24h wait after stop-loss exit before re-entering same expiry."""
        if expiry is None:
            return None

        state = self._load_state()
        now = datetime.now(tz=timezone.utc)
        norm = self._normalize_expiry(expiry)

        for entry in state.get("stop_loss_exits", []):
            if self._normalize_expiry(entry.get("expiry", "")) != norm:
                continue
            exit_time = datetime.fromisoformat(entry["timestamp"])
            if exit_time.tzinfo is None:
                exit_time = exit_time.replace(tzinfo=timezone.utc)
            elapsed = now - exit_time
            if elapsed < timedelta(hours=self.cooling_hours):
                remaining = timedelta(hours=self.cooling_hours) - elapsed
                hours_left = remaining.total_seconds() / 3600
                return (
                    f"COOLING: Stop-loss exit on expiry {norm} was "
                    f"{elapsed.total_seconds() / 3600:.1f}h ago. "
                    f"Wait {hours_left:.1f}h more."
                )
        return None

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    @classmethod
    def record_stop_loss_exit(cls, expiry: str, symbol: str | None = None) -> None:
        """Record a stop-loss exit for cooling enforcement.

        Args:
            expiry: Expiry date string.
            symbol: Optional symbol for logging.
        """
        state = cls._load_state_static()
        exits = state.get("stop_loss_exits", [])
        exits.append({
            "expiry": expiry,
            "symbol": symbol or "",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        })
        state["stop_loss_exits"] = exits
        cls._prune_and_save(state)
        logger.info(f"Recorded stop-loss exit: expiry={expiry} symbol={symbol}")

    @staticmethod
    def _load_state_static() -> dict:
        try:
            if _STATE_FILE.exists():
                return json.loads(_STATE_FILE.read_text())
        except Exception as e:
            logger.warning(f"Failed to load behavioral guard state: {e}")
        return {"stop_loss_exits": []}

    def _load_state(self) -> dict:
        return self._load_state_static()

    @staticmethod
    def _prune_and_save(state: dict) -> None:
        """Remove entries older than _PRUNE_HOURS and persist."""
        now = datetime.now(tz=timezone.utc)
        cutoff = now - timedelta(hours=_PRUNE_HOURS)
        pruned = []
        for entry in state.get("stop_loss_exits", []):
            ts = datetime.fromisoformat(entry["timestamp"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                pruned.append(entry)
        state["stop_loss_exits"] = pruned
        try:
            _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            _STATE_FILE.write_text(json.dumps(state, indent=2))
        except Exception as e:
            logger.warning(f"Failed to save behavioral guard state: {e}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_underlying(symbol: str) -> str:
        try:
            from src.core.trading_constants import extract_underlying
            return extract_underlying(symbol)
        except ImportError:
            return symbol.strip().upper()[:6]

    @staticmethod
    def _normalize_expiry(expiry: str) -> str:
        """Normalize expiry to YYYY-MM-DD for comparison."""
        expiry = expiry.strip()
        if len(expiry) == 6 and expiry.isdigit():
            # YYMMDD -> YYYY-MM-DD
            return f"20{expiry[:2]}-{expiry[2:4]}-{expiry[4:6]}"
        return expiry
