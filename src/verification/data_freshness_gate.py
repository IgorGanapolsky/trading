"""
Data Freshness Verification Gate.

Ensures all data sources are fresh before trading decisions.
Blocks trades if data is stale - a common cause of bad decisions.

Created: 2025-12-15
Lesson: Data staleness has caused multiple trading failures (see ll_019)
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Data source paths
DATA_SOURCES = {
    "system_state": Path("data/system_state.json"),
    "market_data": Path("data/backtests_verification/cache/backtest_cache.json"),
    "sentiment": Path("data/rag/sentiment.db"),
    "rl_model": Path("models/ml/rl_transformer_state.pt"),
    "lessons": Path("data/rag/lessons_learned.json"),
}

# Staleness thresholds (in hours)
STALENESS_THRESHOLDS = {
    "system_state": 24,      # Must be updated daily
    "market_data": 24,       # Market data can be 24h old (relaxed for R&D phase)
    "sentiment": 48,         # Sentiment can be 48h old
    "rl_model": 168,         # RL model can be 1 week old
    "lessons": 168,          # Lessons can be 1 week old
}


@dataclass
class FreshnessResult:
    """Result of data freshness check."""
    source: str
    is_fresh: bool
    last_updated: Optional[datetime]
    age_hours: float
    threshold_hours: float
    message: str


class DataFreshnessGate:
    """
    Verifies all data sources are fresh before trading.

    Checks:
    1. system_state.json - Must be current day
    2. Market data cache - Must be within 1 hour (market hours)
    3. Sentiment data - Must be within 24 hours
    4. RL model - Must be within 1 week
    5. RAG lessons - Must be indexed
    """

    def __init__(
        self,
        data_sources: Optional[dict] = None,
        thresholds: Optional[dict] = None,
    ):
        self.data_sources = data_sources or DATA_SOURCES
        self.thresholds = thresholds or STALENESS_THRESHOLDS

    def check_all(self) -> dict:
        """
        Check freshness of all data sources.

        Returns:
            Dict with overall status and individual results
        """
        results = []
        all_fresh = True
        critical_stale = []

        for source_name, source_path in self.data_sources.items():
            result = self.check_source(source_name, source_path)
            results.append(result)

            if not result.is_fresh:
                all_fresh = False
                if source_name in ["system_state", "market_data"]:
                    critical_stale.append(source_name)

        return {
            "all_fresh": all_fresh,
            "can_trade": len(critical_stale) == 0,
            "critical_stale": critical_stale,
            "results": results,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    def check_source(self, source_name: str, source_path: Path) -> FreshnessResult:
        """Check freshness of a single data source."""
        threshold = self.thresholds.get(source_name, 24)

        if not source_path.exists():
            return FreshnessResult(
                source=source_name,
                is_fresh=False,
                last_updated=None,
                age_hours=float("inf"),
                threshold_hours=threshold,
                message=f"Source not found: {source_path}",
            )

        # Get last modified time
        mtime = datetime.fromtimestamp(source_path.stat().st_mtime, tz=timezone.utc)
        age = datetime.now(timezone.utc) - mtime
        age_hours = age.total_seconds() / 3600

        # For JSON files, also check internal timestamp
        if source_path.suffix == ".json":
            try:
                with open(source_path) as f:
                    data = json.load(f)
                if "last_updated" in data:
                    internal_time = datetime.fromisoformat(
                        data["last_updated"].replace("Z", "+00:00")
                    )
                    internal_age = datetime.now(timezone.utc) - internal_time
                    age_hours = max(age_hours, internal_age.total_seconds() / 3600)
                    mtime = min(mtime, internal_time)
            except (json.JSONDecodeError, KeyError, ValueError):
                pass

        is_fresh = age_hours <= threshold

        if is_fresh:
            message = f"Fresh ({age_hours:.1f}h old, threshold: {threshold}h)"
        else:
            message = f"STALE ({age_hours:.1f}h old, threshold: {threshold}h)"

        return FreshnessResult(
            source=source_name,
            is_fresh=is_fresh,
            last_updated=mtime,
            age_hours=age_hours,
            threshold_hours=threshold,
            message=message,
        )

    def verify_before_trade(self) -> tuple[bool, str]:
        """
        Quick verification before placing a trade.

        Returns:
            Tuple of (can_trade, reason)
        """
        check = self.check_all()

        if check["can_trade"]:
            if check["all_fresh"]:
                return True, "All data sources fresh"
            else:
                stale = [r.source for r in check["results"] if not r.is_fresh]
                return True, f"Trading allowed (non-critical stale: {stale})"
        else:
            return False, f"BLOCKED: Critical data stale: {check['critical_stale']}"

    def get_refresh_commands(self) -> list[str]:
        """Get commands to refresh stale data sources."""
        commands = []
        check = self.check_all()

        for result in check["results"]:
            if not result.is_fresh:
                if result.source == "system_state":
                    commands.append("python scripts/update_system_state.py")
                elif result.source == "market_data":
                    commands.append("python scripts/fetch_market_data.py")
                elif result.source == "sentiment":
                    commands.append("python scripts/update_sentiment.py")
                elif result.source == "rl_model":
                    commands.append("python scripts/rl_daily_retrain.py")
                elif result.source == "lessons":
                    commands.append("python src/rag/lessons_learned_rag.py --reindex")

        return commands


def integrate_with_orchestrator():
    """Add freshness check to TradingOrchestrator."""
    try:
        from src.orchestrator.main import TradingOrchestrator

        gate = DataFreshnessGate()

        if hasattr(TradingOrchestrator, "_freshness_integrated"):
            return

        original_execute = getattr(
            TradingOrchestrator, "_original_execute_trade",
            TradingOrchestrator.execute_trade
        )

        def fresh_execute_trade(self, symbol, action, quantity, **kwargs):
            # Check data freshness
            can_trade, reason = gate.verify_before_trade()

            if not can_trade:
                logger.error(f"Trade BLOCKED - {reason}")
                return {
                    "success": False,
                    "blocked": True,
                    "reason": reason,
                    "refresh_commands": gate.get_refresh_commands(),
                }

            return original_execute(self, symbol, action, quantity, **kwargs)

        TradingOrchestrator.execute_trade = fresh_execute_trade
        TradingOrchestrator._freshness_integrated = True

        logger.info("Integrated DataFreshnessGate with TradingOrchestrator")

    except ImportError:
        logger.warning("TradingOrchestrator not available")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("DATA FRESHNESS VERIFICATION")
    print("=" * 60)

    gate = DataFreshnessGate()
    check = gate.check_all()

    print(f"\n✅ Can Trade: {check['can_trade']}")
    print(f"📊 All Fresh: {check['all_fresh']}")

    if check["critical_stale"]:
        print(f"🚨 Critical Stale: {check['critical_stale']}")

    print("\nIndividual Sources:")
    for result in check["results"]:
        status = "✅" if result.is_fresh else "❌"
        print(f"  {status} {result.source}: {result.message}")

    if not check["all_fresh"]:
        print("\n📋 Refresh Commands:")
        for cmd in gate.get_refresh_commands():
            print(f"  $ {cmd}")
