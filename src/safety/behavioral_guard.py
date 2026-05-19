"""Behavioral Guard - Prevents emotion-driven trading mistakes.

Checks:
1. FOMO: Reject IC entries when SPY moved >2% intraday (inflated premiums, unclear direction)
2. Same-expiry loss block: do not re-enter an expiry after the ledger already recorded a loss
3. Stop-loss cooling: 24h wait after stop-loss exit before re-entering same expiry
4. Blacklist: Belt+suspenders check against TargetSymbols.BLACKLIST

Fails open (allow) when data unavailable — other gates (IV rank, position size) still protect.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from src.core.trading_constants import (
    FOMO_INTRADAY_MOVE_PCT,
    STOP_LOSS_COOLING_HOURS,
    extract_underlying,
)

logger = logging.getLogger(__name__)

_STATE_PATH = Path(__file__).parent.parent.parent / "data" / "behavioral_guard_state.json"
_TRADES_PATH = Path(__file__).parent.parent.parent / "data" / "trades.json"


@dataclass
class BehavioralCheckResult:
    """Result of behavioral guard evaluation."""

    passed: bool
    checks_run: list[str] = field(default_factory=list)
    rejections: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class BehavioralGuard:
    """Prevents emotion-driven trading mistakes."""

    @staticmethod
    def evaluate(
        symbol: str, expiry: str | None = None, spy_change_pct: float | None = None
    ) -> BehavioralCheckResult:
        """Run all behavioral checks.

        Args:
            symbol: Ticker or OCC option symbol.
            expiry: Expiry date string (YYYY-MM-DD) for cooling check.
            spy_change_pct: Absolute intraday SPY move as decimal (e.g. 0.025 = 2.5%).
                           Pass None if unavailable (fails open).

        Returns:
            BehavioralCheckResult with pass/fail and details.
        """
        checks_run: list[str] = []
        rejections: list[str] = []
        warnings: list[str] = []

        # 1. FOMO check
        checks_run.append("fomo_intraday_move")
        if spy_change_pct is not None:
            if abs(spy_change_pct) >= FOMO_INTRADAY_MOVE_PCT:
                rejections.append(
                    f"FOMO blocked: SPY moved {abs(spy_change_pct) * 100:.1f}% intraday "
                    f"(threshold: {FOMO_INTRADAY_MOVE_PCT * 100:.0f}%). "
                    f"Premiums inflated, direction unclear."
                )
        else:
            warnings.append("FOMO check skipped: no intraday data available (fails open)")

        # 2. No same-expiry re-entry after a loss
        checks_run.append("same_expiry_loss_block")
        if expiry:
            recent_loss_msg = BehavioralGuard._check_recent_loss(expiry)
            if recent_loss_msg:
                rejections.append(recent_loss_msg)

        # 3. Stop-loss cooling
        checks_run.append("stop_loss_cooling")
        if expiry:
            cooling_msg = BehavioralGuard._check_cooling(expiry)
            if cooling_msg:
                rejections.append(cooling_msg)

        # 4. Blacklist
        checks_run.append("blacklist")
        underlying = extract_underlying(symbol)
        blacklist_msg = BehavioralGuard._check_blacklist(underlying)
        if blacklist_msg:
            rejections.append(blacklist_msg)

        return BehavioralCheckResult(
            passed=len(rejections) == 0,
            checks_run=checks_run,
            rejections=rejections,
            warnings=warnings,
        )

    @staticmethod
    def _check_cooling(expiry: str) -> str | None:
        """Check if expiry is in cooling period after a recent stop-loss."""
        state = BehavioralGuard._load_state()
        now = datetime.now()
        cooling_cutoff = now - timedelta(hours=STOP_LOSS_COOLING_HOURS)

        for entry in state.get("stop_loss_exits", []):
            if entry.get("expiry") != expiry:
                continue
            exit_time = datetime.fromisoformat(entry["timestamp"])
            if exit_time > cooling_cutoff:
                hours_ago = (now - exit_time).total_seconds() / 3600
                remaining = STOP_LOSS_COOLING_HOURS - hours_ago
                return (
                    f"Cooling period: stop-loss on expiry {expiry} was {hours_ago:.0f}h ago. "
                    f"Wait {remaining:.0f}h more (policy: {STOP_LOSS_COOLING_HOURS}h)."
                )
        return None

    @staticmethod
    def _check_recent_loss(expiry: str) -> str | None:
        """Block same-expiry re-entry once the closed-trade ledger shows a loss."""
        try:
            if not _TRADES_PATH.exists():
                return None
            payload = json.loads(_TRADES_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning(f"Could not load closed-trade ledger for behavioral guard: {exc}")
            return None

        trades = payload.get("trades", []) if isinstance(payload, dict) else []
        matching_losses: list[dict] = []
        for trade in trades:
            if not isinstance(trade, dict):
                continue
            if str(trade.get("strategy", "")).lower() != "iron_condor":
                continue
            if str(trade.get("status", "")).lower() != "closed":
                continue
            trade_expiry = (
                str((trade.get("legs") or {}).get("expiry") or "").strip()
                if isinstance(trade.get("legs"), dict)
                else ""
            )
            if trade_expiry != expiry:
                continue

            outcome = str(trade.get("outcome", "")).lower()
            realized_pnl = trade.get("realized_pnl")
            try:
                pnl_value = float(realized_pnl)
            except (TypeError, ValueError):
                pnl_value = 0.0
            if outcome == "loss" or pnl_value < 0:
                matching_losses.append(trade)

        if not matching_losses:
            return None

        matching_losses.sort(
            key=lambda row: str(row.get("exit_time") or row.get("exit_date") or "")
        )
        latest = matching_losses[-1]
        latest_exit = str(latest.get("exit_time") or latest.get("exit_date") or "unknown time")
        latest_pnl = latest.get("realized_pnl")
        return (
            f"Recent-loss block: expiry {expiry} already closed as a loss "
            f"(last exit {latest_exit}, P/L {latest_pnl}). "
            "Validation mode forbids same-expiry re-entry."
        )

    @staticmethod
    def _check_blacklist(underlying: str) -> str | None:
        """Belt+suspenders blacklist check."""
        try:
            from src.constants.trading_thresholds import TargetSymbols

            if underlying.upper() in [s.upper() for s in TargetSymbols.BLACKLIST]:
                return f"Blacklisted ticker: {underlying} is in TargetSymbols.BLACKLIST"
        except ImportError:
            pass  # No blacklist module = no block
        return None

    @staticmethod
    def record_stop_loss_exit(expiry: str) -> None:
        """Record a stop-loss exit for cooling enforcement.

        Call this from the position manager when a stop-loss triggers.
        """
        state = BehavioralGuard._load_state()
        exits = state.get("stop_loss_exits", [])
        exits.append(
            {
                "expiry": expiry,
                "timestamp": datetime.now().isoformat(),
            }
        )
        # Prune entries older than the cooling window (never tighter than 48h).
        # A hardcoded 48h prune silently dropped cooling records before the
        # actual cooling window expired whenever STOP_LOSS_COOLING_HOURS was
        # configured above 48 — defeating the cooling guard.
        prune_hours = max(STOP_LOSS_COOLING_HOURS, 48)
        cutoff = datetime.now() - timedelta(hours=prune_hours)
        exits = [e for e in exits if datetime.fromisoformat(e["timestamp"]) > cutoff]
        state["stop_loss_exits"] = exits
        BehavioralGuard._save_state(state)
        logger.info(
            f"Recorded stop-loss exit for expiry {expiry} (cooling: {STOP_LOSS_COOLING_HOURS}h)"
        )

    @staticmethod
    def _load_state() -> dict:
        try:
            if _STATE_PATH.exists():
                with open(_STATE_PATH) as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load behavioral guard state: {e}")
        return {"stop_loss_exits": []}

    @staticmethod
    def _save_state(state: dict) -> None:
        try:
            _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(_STATE_PATH, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save behavioral guard state: {e}")
