"""Bias Store - Stores market bias analysis snapshots."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class BiasSnapshot:
    """A snapshot of market bias at a point in time."""

    timestamp: datetime
    bias: str  # "bullish", "bearish", "neutral"
    confidence: float
    source: str = "unknown"
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "bias": self.bias,
            "confidence": self.confidence,
            "source": self.source,
            "metadata": self.metadata,
        }


class BiasProvider:
    """Provides market bias signals."""

    def __init__(self):
        self.current_bias = "neutral"
        self.confidence = 0.5

    def get_bias(self) -> BiasSnapshot:
        """Get current market bias."""
        return BiasSnapshot(
            timestamp=datetime.now(),
            bias=self.current_bias,
            confidence=self.confidence,
            source="provider",
        )


class BiasStore:
    """Persists bias snapshots to disk."""

    def __init__(self, bias_dir: Optional[Path | str] = None):
        # Handle both str and Path inputs (CEO FIX Jan 15, 2026)
        if bias_dir is None:
            self.bias_dir = Path("data/bias")
        elif isinstance(bias_dir, str):
            self.bias_dir = Path(bias_dir)
        else:
            self.bias_dir = bias_dir
        self.bias_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots: list[BiasSnapshot] = []

    def persist(self, snapshot: BiasSnapshot) -> None:
        """Save a bias snapshot."""
        self.snapshots.append(snapshot)
        filepath = self.bias_dir / f"bias_{snapshot.timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        with open(filepath, "w") as f:
            json.dump(snapshot.to_dict(), f, indent=2)

    def get_latest(self) -> Optional[BiasSnapshot]:
        """Get most recent bias snapshot."""
        if self.snapshots:
            return self.snapshots[-1]
        return None
