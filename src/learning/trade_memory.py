"""Trade Memory - Stores and retrieves trade patterns for learning."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass
class TradePattern:
    """A trade pattern with outcome."""

    symbol: str
    strategy: str
    entry_reason: str
    pnl: float
    won: bool
    timestamp: str
    pattern_features: dict[str, Any]


class TradeMemory:
    """Memory store for trade patterns and outcomes."""

    def __init__(self, memory_path: Path | None = None):
        self.memory_path = memory_path or Path("data/trade_memory.json")
        self.patterns: list[TradePattern] = []
        self._load()

    def _load(self) -> None:
        """Load patterns from disk."""
        if not self.memory_path.exists():
            return
        try:
            payload = json.loads(self.memory_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        raw_patterns = payload.get("patterns", []) if isinstance(payload, dict) else []
        if not isinstance(raw_patterns, list):
            return
        loaded: list[TradePattern] = []
        for item in raw_patterns:
            if not isinstance(item, dict):
                continue
            loaded.append(
                TradePattern(
                    symbol=str(item.get("symbol", "")),
                    strategy=str(item.get("strategy", "unknown")),
                    entry_reason=str(item.get("entry_reason", "unknown")),
                    pnl=float(item.get("pnl", 0.0)),
                    won=bool(item.get("won", False)),
                    timestamp=str(item.get("timestamp") or _utc_now_iso()),
                    pattern_features=item.get("pattern_features", {}) or {},
                )
            )
        self.patterns = loaded

    def save(self) -> None:
        """Save patterns to disk."""
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "patterns": [asdict(pattern) for pattern in self.patterns],
            "updated_at": _utc_now_iso(),
        }
        self.memory_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def add_pattern(self, pattern: TradePattern) -> None:
        """Add a pattern to memory."""
        self.patterns.append(pattern)
        self.save()

    def add_trade(self, trade: dict[str, Any]) -> None:
        """Add a trade record dict to memory (convenience wrapper)."""
        pnl = float(trade.get("pnl", 0.0))
        won = bool(trade.get("won")) if "won" in trade else pnl > 0
        pattern = TradePattern(
            symbol=str(trade.get("symbol", "")),
            strategy=str(trade.get("strategy", "unknown")),
            entry_reason=str(trade.get("entry_reason", trade.get("reason", "unknown"))),
            pnl=pnl,
            won=won,
            timestamp=str(trade.get("timestamp") or _utc_now_iso()),
            pattern_features=trade,
        )
        self.add_pattern(pattern)

    def query_similar(
        self, strategy: str, entry_reason: str, symbol: str | None = None
    ) -> dict[str, Any]:
        """Query historical outcomes for matching strategy pattern."""
        strategy_key = (strategy or "unknown").strip().lower()
        reason_key = (entry_reason or "unknown").strip().lower()
        symbol_key = (symbol or "").strip().upper()

        exact = [
            p
            for p in self.patterns
            if p.strategy.lower() == strategy_key and p.entry_reason.lower() == reason_key
        ]
        by_strategy = [p for p in self.patterns if p.strategy.lower() == strategy_key]
        by_symbol = [p for p in by_strategy if symbol_key and p.symbol.upper() == symbol_key]

        if exact:
            matches = exact
            match_type = "strategy_entry_reason"
        elif by_symbol:
            matches = by_symbol
            match_type = "strategy_symbol"
        else:
            matches = by_strategy
            match_type = "strategy_only"

        sample_size = len(matches)
        wins = sum(1 for p in matches if p.won)
        losses = sample_size - wins
        total_pnl = sum(float(p.pnl) for p in matches)
        win_rate = (wins / sample_size) if sample_size > 0 else 0.5
        avg_pnl = (total_pnl / sample_size) if sample_size > 0 else 0.0

        if sample_size == 0:
            recommendation = "NO_HISTORY"
        elif sample_size < 3:
            recommendation = "INSUFFICIENT_DATA"
        elif win_rate >= 0.7 and avg_pnl > 0:
            recommendation = "STRONG_PROCEED"
        elif win_rate >= 0.55:
            recommendation = "PROCEED"
        elif win_rate < 0.4:
            recommendation = "STRONG_AVOID"
        elif win_rate < 0.5:
            recommendation = "AVOID"
        else:
            recommendation = "NEUTRAL"

        return {
            "pattern": f"{strategy_key}_{reason_key}",
            "found": sample_size > 0,
            "sample_size": sample_size,
            "win_rate": win_rate,
            "wins": wins,
            "losses": losses,
            "total_pnl": total_pnl,
            "avg_pnl": avg_pnl,
            "recommendation": recommendation,
            "match_type": match_type,
        }

    def get_similar_patterns(self, features: dict[str, Any], limit: int = 5) -> list[TradePattern]:
        """Find similar historical patterns."""
        strategy = str(features.get("strategy", "unknown"))
        entry_reason = str(features.get("entry_reason", features.get("reason", "unknown")))
        symbol = str(features.get("symbol", "")) or None
        result = self.query_similar(strategy, entry_reason, symbol=symbol)
        if not result.get("found"):
            return []
        exact = [
            p
            for p in self.patterns
            if p.strategy.lower() == strategy.lower()
            and p.entry_reason.lower() == entry_reason.lower()
        ]
        if not exact:
            exact = [p for p in self.patterns if p.strategy.lower() == strategy.lower()]
        return exact[: max(0, int(limit))]

    def get_win_rate_for_pattern(self, features: dict[str, Any]) -> float:
        """Calculate win rate for similar patterns."""
        strategy = str(features.get("strategy", "unknown"))
        entry_reason = str(features.get("entry_reason", features.get("reason", "unknown")))
        symbol = str(features.get("symbol", "")) or None
        result = self.query_similar(strategy, entry_reason, symbol=symbol)
        return float(result.get("win_rate", 0.5))
