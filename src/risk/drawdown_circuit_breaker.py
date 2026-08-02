"""Automated Real-Time Intraday Equity Drawdown Circuit Breaker.

Monitors portfolio equity relative to daily peak equity. If intraday drawdown
exceeds the configured threshold (default: 5.0%), automatically trips the
data/TRADING_HALTED file kill-switch to halt trade execution.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
HALT_FILE_PATH = ROOT / "data" / "TRADING_HALTED"
CIRCUIT_LOG_PATH = ROOT / "data" / "audit" / "circuit_breaker_log.json"

DEFAULT_MAX_INTRADAY_DRAWDOWN_PCT = 5.0  # 5% max intraday drawdown threshold


@dataclass(frozen=True)
class CircuitBreakerStatus:
    tripped: bool
    current_equity: float
    peak_equity: float
    drawdown_pct: float
    max_allowed_drawdown_pct: float
    reason: str | None = None


class DrawdownCircuitBreaker:
    """Monitors intraday drawdown and automatically trips the system halt file."""

    def __init__(self, max_drawdown_pct: float = DEFAULT_MAX_INTRADAY_DRAWDOWN_PCT):
        self.max_drawdown_pct = max_drawdown_pct

    def check_equity(
        self,
        current_equity: float,
        peak_equity: float,
        *,
        persist: bool = True,
    ) -> CircuitBreakerStatus:
        """Check current equity against peak equity.

        When ``persist`` is True (default), a trip writes ``data/TRADING_HALTED``
        and the circuit-breaker audit log. Callers that only *simulate* a trip
        (eval harness, unit tests that assert logic without side effects) MUST
        pass ``persist=False`` so synthetic equity numbers cannot halt production.
        """
        if peak_equity <= 0:
            return CircuitBreakerStatus(
                tripped=False,
                current_equity=current_equity,
                peak_equity=peak_equity,
                drawdown_pct=0.0,
                max_allowed_drawdown_pct=self.max_drawdown_pct,
            )

        drawdown_pct = ((peak_equity - current_equity) / peak_equity) * 100.0
        drawdown_pct = max(0.0, drawdown_pct)

        if drawdown_pct >= self.max_drawdown_pct:
            reason = (
                f"INTRADAY_DRAWDOWN_EXCEEDED: Current equity ${current_equity:.2f} is "
                f"{drawdown_pct:.2f}% below peak ${peak_equity:.2f} "
                f"(max allowed: {self.max_drawdown_pct:.2f}%)."
            )
            if persist:
                self._trip_circuit_breaker(reason, current_equity, peak_equity, drawdown_pct)
            else:
                logger.info(
                    "Circuit breaker would trip (persist=False): %s",
                    reason,
                )
            return CircuitBreakerStatus(
                tripped=True,
                current_equity=current_equity,
                peak_equity=peak_equity,
                drawdown_pct=round(drawdown_pct, 2),
                max_allowed_drawdown_pct=self.max_drawdown_pct,
                reason=reason,
            )

        return CircuitBreakerStatus(
            tripped=False,
            current_equity=current_equity,
            peak_equity=peak_equity,
            drawdown_pct=round(drawdown_pct, 2),
            max_allowed_drawdown_pct=self.max_drawdown_pct,
        )

    def _trip_circuit_breaker(
        self, reason: str, current_equity: float, peak_equity: float, drawdown_pct: float
    ) -> None:
        logger.critical("🚨 CIRCUIT BREAKER TRIPPED: %s", reason)

        # 1. Create data/TRADING_HALTED file kill-switch
        HALT_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        halt_content = f"TRADING_HALTED at {datetime.now(UTC).isoformat()}\nReason: {reason}\n"
        HALT_FILE_PATH.write_text(halt_content, encoding="utf-8")

        # 2. Append to audit log
        CIRCUIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "tripped_at": datetime.now(UTC).isoformat(),
            "reason": reason,
            "current_equity": current_equity,
            "peak_equity": peak_equity,
            "drawdown_pct": round(drawdown_pct, 2),
        }
        logs = []
        if CIRCUIT_LOG_PATH.exists():
            try:
                with CIRCUIT_LOG_PATH.open("r", encoding="utf-8") as h:
                    logs = json.load(h)
            except Exception:
                logs = []
        logs.append(record)
        with CIRCUIT_LOG_PATH.open("w", encoding="utf-8") as h:
            json.dump(logs[-50:], h, indent=2)
