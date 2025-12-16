from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from src.core.config import AppConfig, load_config

logger = logging.getLogger(__name__)


_DEFAULT_BUCKET_TICKERS = {
    "core_etfs": ["SPY", "QQQ", "VTI", "VOO"],
    "growth_stocks": ["NVDA", "TSLA", "AMZN", "GOOGL", "MSFT"],
    "bonds_treasuries": ["BIL", "BND", "SHY", "IEF", "TLT"],
    "reits": ["VNQ", "SCHH"],
    "options_reserve": [],
}


def _load_custom_bucket_map() -> dict[str, list[str]]:
    """Allow overrides via SMART_DCA_BUCKETS env (JSON)."""
    raw = os.getenv("SMART_DCA_BUCKETS")
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("SMART_DCA_BUCKETS malformed JSON: %s", exc)
        return {}
    overrides: dict[str, list[str]] = {}
    for bucket, tickers in payload.items():
        if not isinstance(tickers, Iterable):
            continue
        overrides[bucket] = [str(t).upper() for t in tickers]
    return overrides


def _build_ticker_index(mapping: dict[str, list[str]]) -> dict[str, str]:
    index: dict[str, str] = {}
    for bucket, tickers in mapping.items():
        for ticker in tickers:
            index[ticker.upper()] = bucket
    return index


@dataclass
class AllocationPlan:
    ticker: str
    bucket: str
    cap: float
    confidence: float


@dataclass
class SafeSweep:
    symbol: str
    amount: float
    buckets: dict[str, float]


class SmartDCAAllocator:
    """
    Tracks the $10/day budget and routes unused cash into a safety bucket.

    Each bucket inherits its daily dollar target from `AppConfig.get_tier_allocations()`.
    Whenever a trade is approved, we mark that bucket as spent. Any remainder is
    swept into the configured T-Bill / cash proxy (default: BIL).
    """

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or load_config()
        self.safe_symbol = os.getenv("SMART_DCA_SAFE_SYMBOL", "BIL").upper()
        self._bucket_targets = self._resolve_bucket_targets()
        self._bucket_spend = {bucket: 0.0 for bucket in self._bucket_targets}
        overrides = _load_custom_bucket_map()
        bucket_map = dict(_DEFAULT_BUCKET_TICKERS)
        bucket_map.update({k: [s.upper() for s in v] for k, v in overrides.items()})
        self._ticker_to_bucket = _build_ticker_index(bucket_map)
        self._min_trade = float(os.getenv("SMART_DCA_MIN_TRADE", "1.0"))
        self._session_tickers: list[str] = []

    # ------------------------------------------------------------------ #
    # Session lifecycle
    # ------------------------------------------------------------------ #
    def reset_session(self, tickers: Iterable[str]) -> None:
        self._bucket_targets = self._resolve_bucket_targets()
        self._bucket_spend = {bucket: 0.0 for bucket in self._bucket_targets}
        self._session_tickers = [ticker.upper() for ticker in tickers]
        logger.info(
            "Smart DCA reset: $%.2f/day across %d buckets",
            sum(self._bucket_targets.values()),
            len(self._bucket_targets),
        )

    # ------------------------------------------------------------------ #
    # Allocation helpers
    # ------------------------------------------------------------------ #
    def plan_allocation(
        self,
        *,
        ticker: str,
        momentum_strength: float,
        rl_confidence: float,
        sentiment_score: float,
    ) -> AllocationPlan:
        bucket = self._bucket_for_ticker(ticker)
        target = self._bucket_targets.get(bucket, 0.0)
        remaining = max(0.0, target - self._bucket_spend.get(bucket, 0.0))
        blended_confidence = self._blend_confidence(
            momentum_strength, rl_confidence, sentiment_score
        )
        cap = round(remaining * blended_confidence, 2)
        if cap < self._min_trade:
            cap = 0.0
        return AllocationPlan(
            ticker=ticker.upper(),
            bucket=bucket,
            cap=cap,
            confidence=blended_confidence,
        )

    def reserve(self, bucket: str, amount: float) -> None:
        target = self._bucket_targets.get(bucket, 0.0)
        new_value = min(target, self._bucket_spend.get(bucket, 0.0) + max(0.0, amount))
        self._bucket_spend[bucket] = round(new_value, 2)

    def release(self, bucket: str, amount: float) -> None:
        current = self._bucket_spend.get(bucket, 0.0)
        self._bucket_spend[bucket] = round(max(0.0, current - max(0.0, amount)), 2)

    def drain_to_safe(self) -> SafeSweep | None:
        leftovers: dict[str, float] = {}
        total = 0.0
        for bucket, target in self._bucket_targets.items():
            remaining = max(0.0, target - self._bucket_spend.get(bucket, 0.0))
            if remaining <= 0:
                continue
            leftovers[bucket] = round(remaining, 2)
            total += remaining
            self._bucket_spend[bucket] = target

        total = round(total, 2)
        if total <= 0:
            return None

        return SafeSweep(symbol=self.safe_symbol, amount=total, buckets=leftovers)

    def reallocate_all_to_bucket(self, bucket: str) -> float:
        """
        Move the entire session budget into a single bucket.

        Used for weekend/holiday sessions where only a subset of tickers (e.g. crypto proxies)
        are tradable. Returns the reallocated budget for diagnostics.
        """
        normalized = bucket.strip().lower()
        if not normalized:
            raise ValueError("bucket name is required")

        total_budget = round(sum(self._bucket_targets.values()), 2)
        if normalized not in self._bucket_targets:
            self._bucket_targets[normalized] = 0.0
            self._bucket_spend[normalized] = 0.0

        for key in list(self._bucket_targets.keys()):
            self._bucket_targets[key] = 0.0
            self._bucket_spend[key] = 0.0

        self._bucket_targets[normalized] = total_budget
        logger.info(
            "Smart DCA reallocated $%.2f of daily budget to %s bucket", total_budget, normalized
        )
        return total_budget

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _resolve_bucket_targets(self) -> dict[str, float]:
        allocations = self.config.get_tier_allocations()
        # Normalize keys for downstream logging
        normalized = {bucket: round(float(amount), 2) for bucket, amount in allocations.items()}
        return normalized

    def _bucket_for_ticker(self, ticker: str) -> str:
        symbol = ticker.upper()
        if symbol in self._ticker_to_bucket:
            return self._ticker_to_bucket[symbol]
        # Default fallback: treat unknown tickers as growth to stay conservative
        default_bucket = "growth_stocks" if symbol not in {"SPY", "QQQ"} else "core_etfs"
        self._ticker_to_bucket[symbol] = default_bucket
        return default_bucket

    @staticmethod
    def _blend_confidence(strength: float, rl_conf: float, sentiment: float) -> float:
        """Convert gate signals into a 0-1 weighting factor."""
        safe_strength = max(0.0, min(1.0, strength))
        safe_rl = max(0.0, min(1.0, rl_conf))
        safe_sentiment = max(-1.0, min(1.0, sentiment))
        base = 0.2 + 0.5 * safe_strength + 0.4 * safe_rl + 0.2 * max(0.0, safe_sentiment)
        return max(0.0, min(1.0, base))

    # ------------------------------------------------------------------ #
    # Diagnostics
    # ------------------------------------------------------------------ #
    def remaining_budget(self) -> dict[str, float]:
        return {
            bucket: round(max(0.0, target - self._bucket_spend[bucket]), 2)
            for bucket, target in self._bucket_targets.items()
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "targets": self._bucket_targets,
            "spent": self._bucket_spend,
            "remaining": self.remaining_budget(),
            "safe_symbol": self.safe_symbol,
            "session_tickers": self._session_tickers,
        }
