"""
Economic guardrails built on Finnhub to prevent trading through market-moving events.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from src.utils.finnhub_client import FinnhubClient

logger = logging.getLogger(__name__)


class EconomicGuardrails:
    """Caches Finnhub economic/earnings events and exposes blocking decisions."""

    def __init__(
        self,
        symbols: Iterable[str],
        cache_path: Path = Path("data/economic_guardrails.json"),
        ttl_minutes: int = 240,
    ) -> None:
        self.symbols = sorted(set(sym.upper() for sym in symbols))
        self.cache_path = cache_path
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(minutes=ttl_minutes)
        self.client = FinnhubClient()
        self._data = self._load_cache()
        if self._should_refresh():
            self._refresh()

    def is_market_blocked(self) -> Tuple[bool, Optional[str]]:
        blockers = self._data.get("market_blockers", [])
        if not blockers:
            return False, None
        return True, blockers[0].get("description")

    def is_symbol_blocked(self, symbol: str) -> Tuple[bool, Optional[str]]:
        symbol = symbol.upper()
        blockers = self._data.get("symbol_blockers", {}).get(symbol, [])
        if not blockers:
            return False, None
        return True, blockers[0].get("description")

    def summary(self) -> Dict[str, List[Dict[str, str]]]:
        return {
            "market_blockers": self._data.get("market_blockers", []),
            "symbol_blockers": self._data.get("symbol_blockers", {}),
        }

    # Internal helpers -------------------------------------------------

    def _should_refresh(self) -> bool:
        generated_at = self._data.get("generated_at")
        if not generated_at:
            return True
        try:
            ts = datetime.fromisoformat(generated_at)
        except ValueError:
            return True
        return datetime.utcnow() - ts > self.ttl

    def _refresh(self) -> None:
        """Fetch latest events from Finnhub and update cache."""
        today = date.today()
        market_blockers = self._fetch_major_events(today, today + timedelta(days=1))
        symbol_blockers = self._fetch_symbol_events(today, today + timedelta(days=7))

        self._data = {
            "generated_at": datetime.utcnow().isoformat(),
            "market_blockers": market_blockers,
            "symbol_blockers": symbol_blockers,
        }
        self._save_cache()

    def _fetch_major_events(self, start: date, end: date) -> List[Dict[str, str]]:
        blockers: List[Dict[str, str]] = []
        events = self.client.get_economic_calendar(start, end)
        for event in events:
            event_name = event.get("event", "")
            if not event_name:
                continue
            blockers.append(
                {
                    "date": event.get("date", start.strftime("%Y-%m-%d")),
                    "description": event_name,
                    "impact": event.get("impact", "medium"),
                }
            )
        if blockers:
            logger.info("Economic guardrail loaded %d market events", len(blockers))
        return blockers

    def _fetch_symbol_events(
        self, start: date, end: date
    ) -> Dict[str, List[Dict[str, str]]]:
        blockers: Dict[str, List[Dict[str, str]]] = {}
        earnings = self.client.get_earnings_calendar(start, end)
        if not earnings:
            return blockers

        symbol_lookup = set(self.symbols)
        for entry in earnings:
            symbol = entry.get("symbol", "").upper()
            if symbol not in symbol_lookup:
                continue
            blockers.setdefault(symbol, []).append(
                {
                    "date": entry.get("date", start.strftime("%Y-%m-%d")),
                    "description": f"Earnings {symbol}",
                    "time": entry.get("time", "TBD"),
                }
            )
        if blockers:
            logger.info("Economic guardrail tracking events for %d symbols", len(blockers))
        return blockers

    def _load_cache(self) -> Dict:
        if not self.cache_path.exists():
            return {}
        try:
            with open(self.cache_path, "r", encoding="utf-8") as fp:
                return json.load(fp)
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Failed to read guardrail cache: %s", exc)
            return {}

    def _save_cache(self) -> None:
        with open(self.cache_path, "w", encoding="utf-8") as fp:
            json.dump(self._data, fp, indent=2)
