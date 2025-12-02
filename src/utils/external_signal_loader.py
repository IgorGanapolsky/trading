"""
Utilities for saving and loading external trading signals from open sources.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

EXTERNAL_SIGNAL_DIR = Path("data/external_signals")
EXTERNAL_SIGNAL_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ExternalSignal:
    ticker: str
    score: float  # -100 (bearish) to +100 (bullish)
    confidence: float  # 0-1
    source: str
    signal_type: str
    timestamp: datetime
    notes: str | None = None

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker.upper(),
            "score": self.score,
            "confidence": self.confidence,
            "source": self.source,
            "signal_type": self.signal_type,
            "timestamp": self.timestamp.astimezone(timezone.utc).isoformat(),
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ExternalSignal:
        return cls(
            ticker=data["ticker"],
            score=float(data.get("score", 0.0)),
            confidence=float(data.get("confidence", 0.0)),
            source=data.get("source", "unknown"),
            signal_type=data.get("signal_type", "unspecified"),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            notes=data.get("notes"),
        )


def save_signals(signals: list[ExternalSignal], metadata: dict | None = None) -> Path:
    """
    Persist a batch of signals to disk.
    """
    if not signals:
        raise ValueError("Cannot save empty signal batch")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    file_path = EXTERNAL_SIGNAL_DIR / f"signals_{timestamp}.json"
    payload = {
        "meta": metadata or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "count": len(signals),
        "signals": [signal.to_dict() for signal in signals],
    }

    with file_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    logger.info("Saved %d external signals to %s", len(signals), file_path)
    return file_path


def list_signal_files(limit: int | None = None) -> list[Path]:
    files = sorted(
        EXTERNAL_SIGNAL_DIR.glob("signals_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if limit:
        return files[:limit]
    return files


def load_signals_file(path: Path) -> dict[str, dict]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    signals = payload.get("signals", [])
    return {entry["ticker"].upper(): entry for entry in signals}


def load_latest_signals() -> dict[str, dict]:
    files = list_signal_files(limit=1)
    if not files:
        return {}
    try:
        return load_signals_file(files[0])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load latest external signals: %s", exc)
        return {}


def get_signal_for_ticker(ticker: str, signals: dict[str, dict] | None = None) -> dict | None:
    if not ticker:
        return None
    signals = signals or load_latest_signals()
    return signals.get(ticker.upper())
