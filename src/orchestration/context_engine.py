"""
Context Engineering Module
Offloads context from prompts to persistent storage for better agent performance
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Singleton instance
_context_engine_instance = None


class MemoryTimescale(Enum):
    """Memory timescales for context retention"""

    IMMEDIATE = "immediate"  # Current session
    DAILY = "daily"  # Today's context
    EPISODIC = "episodic"  # Important events
    SEMANTIC = "semantic"  # Long-term patterns


@dataclass
class ContextMemory:
    """Memory entry for agent context"""

    key: str
    value: Any
    timescale: MemoryTimescale
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


def get_context_engine() -> "ContextEngine":
    """Get or create singleton ContextEngine instance"""
    global _context_engine_instance
    if _context_engine_instance is None:
        _context_engine_instance = ContextEngine()
    return _context_engine_instance


@dataclass
class ContextEntry:
    """Context entry for persistent storage"""

    key: str
    data: dict[str, Any]
    timestamp: str
    agent_type: str
    ttl_seconds: int | None = None
    tags: list[str] = None


class ContextEngine:
    """
    Context Engineering Engine

    Offloads context from prompts to persistent storage:
    - Trade logs
    - Backtest results
    - Audit trails
    - Agent decisions
    - Market data snapshots
    """

    def __init__(self, base_dir: Path = Path("data/agent_context")):
        """
        Initialize Context Engine

        Args:
            base_dir: Base directory for context storage
        """
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # Context storage directories
        self.trade_logs_dir = self.base_dir / "trade_logs"
        self.backtest_dir = self.base_dir / "backtests"
        self.audit_dir = self.base_dir / "audit"
        self.market_data_dir = self.base_dir / "market_data"
        self.agent_decisions_dir = self.base_dir / "decisions"

        # Create directories
        for dir_path in [
            self.trade_logs_dir,
            self.backtest_dir,
            self.audit_dir,
            self.market_data_dir,
            self.agent_decisions_dir,
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"✅ Context Engine initialized: {self.base_dir}")

    def save_trade_log(self, trade_data: dict[str, Any]) -> str:
        """
        Save trade log to persistent storage

        Args:
            trade_data: Trade data to save

        Returns:
            File path of saved log
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        symbol = trade_data.get("symbol", "UNKNOWN")
        filename = f"{symbol}_{timestamp}.json"
        filepath = self.trade_logs_dir / filename

        entry = ContextEntry(
            key=f"trade_{symbol}_{timestamp}",
            data=trade_data,
            timestamp=datetime.now().isoformat(),
            agent_type=trade_data.get("agent_type", "unknown"),
            tags=["trade", symbol],
        )

        with open(filepath, "w") as f:
            json.dump(asdict(entry), f, indent=2, default=str)

        logger.debug(f"Saved trade log: {filepath}")
        return str(filepath)

    def save_backtest_result(self, backtest_data: dict[str, Any]) -> str:
        """
        Save backtest result

        Args:
            backtest_data: Backtest data to save

        Returns:
            File path of saved result
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        strategy = backtest_data.get("strategy", "unknown")
        filename = f"{strategy}_{timestamp}.json"
        filepath = self.backtest_dir / filename

        entry = ContextEntry(
            key=f"backtest_{strategy}_{timestamp}",
            data=backtest_data,
            timestamp=datetime.now().isoformat(),
            agent_type="backtest",
            tags=["backtest", strategy],
        )

        with open(filepath, "w") as f:
            json.dump(asdict(entry), f, indent=2, default=str)

        logger.debug(f"Saved backtest result: {filepath}")
        return str(filepath)

    def save_agent_decision(self, decision_data: dict[str, Any]) -> str:
        """
        Save agent decision for traceability

        Args:
            decision_data: Decision data to save

        Returns:
            File path of saved decision
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        agent_type = decision_data.get("agent_type", "unknown")
        symbol = decision_data.get("symbol", "UNKNOWN")
        filename = f"{agent_type}_{symbol}_{timestamp}.json"
        filepath = self.agent_decisions_dir / filename

        entry = ContextEntry(
            key=f"decision_{agent_type}_{symbol}_{timestamp}",
            data=decision_data,
            timestamp=datetime.now().isoformat(),
            agent_type=agent_type,
            tags=["decision", agent_type, symbol],
        )

        with open(filepath, "w") as f:
            json.dump(asdict(entry), f, indent=2, default=str)

        logger.debug(f"Saved agent decision: {filepath}")
        return str(filepath)

    def load_recent_trades(self, symbol: str | None = None, days: int = 7) -> list[dict[str, Any]]:
        """
        Load recent trades from storage

        Args:
            symbol: Filter by symbol (optional)
            days: Number of days to look back

        Returns:
            List of trade logs
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        trades = []

        for filepath in self.trade_logs_dir.glob("*.json"):
            try:
                with open(filepath) as f:
                    entry = json.load(f)
                    entry_timestamp = datetime.fromisoformat(entry["timestamp"])

                    if entry_timestamp >= cutoff_date:
                        if symbol is None or symbol in entry.get("tags", []):
                            trades.append(entry["data"])
            except Exception as e:
                logger.warning(f"Error loading trade log {filepath}: {e}")

        return sorted(trades, key=lambda x: x.get("timestamp", ""), reverse=True)

    def load_agent_decisions(
        self,
        agent_type: str | None = None,
        symbol: str | None = None,
        days: int = 7,
    ) -> list[dict[str, Any]]:
        """
        Load recent agent decisions

        Args:
            agent_type: Filter by agent type (optional)
            symbol: Filter by symbol (optional)
            days: Number of days to look back

        Returns:
            List of agent decisions
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        decisions = []

        for filepath in self.agent_decisions_dir.glob("*.json"):
            try:
                with open(filepath) as f:
                    entry = json.load(f)
                    entry_timestamp = datetime.fromisoformat(entry["timestamp"])

                    if entry_timestamp >= cutoff_date:
                        data = entry["data"]
                        if (agent_type is None or data.get("agent_type") == agent_type) and (
                            symbol is None or data.get("symbol") == symbol
                        ):
                            decisions.append(data)
            except Exception as e:
                logger.warning(f"Error loading decision {filepath}: {e}")

        return sorted(decisions, key=lambda x: x.get("timestamp", ""), reverse=True)

    def get_context_summary(self, symbol: str, days: int = 30) -> dict[str, Any]:
        """
        Get context summary for a symbol (for prompt injection)

        Args:
            symbol: Symbol to summarize
            days: Days to look back

        Returns:
            Context summary dictionary
        """
        trades = self.load_recent_trades(symbol=symbol, days=days)
        decisions = self.load_agent_decisions(symbol=symbol, days=days)

        # Calculate summary statistics
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t.get("pnl", 0) > 0)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        total_pnl = sum(t.get("pnl", 0) for t in trades)

        # Agent decision breakdown
        agent_decisions = {}
        for decision in decisions:
            agent_type = decision.get("agent_type", "unknown")
            if agent_type not in agent_decisions:
                agent_decisions[agent_type] = []
            agent_decisions[agent_type].append(decision)

        return {
            "symbol": symbol,
            "period_days": days,
            "summary": {
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "win_rate_pct": win_rate,
                "total_pnl": total_pnl,
                "agent_decisions_count": len(decisions),
            },
            "recent_trades": trades[:10],  # Last 10 trades
            "agent_decisions": agent_decisions,
            "context_files": {
                "trade_logs": len(list(self.trade_logs_dir.glob(f"{symbol}_*.json"))),
                "decisions": len([d for d in decisions if d.get("symbol") == symbol]),
            },
        }

    def export_context(self, output_file: Path, symbol: str | None = None, days: int = 30) -> str:
        """
        Export context for analysis (bulk import/export)

        Args:
            output_file: Output file path
            symbol: Filter by symbol (optional)
            days: Days to export

        Returns:
            Path to exported file
        """
        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "days": days,
            "trades": self.load_recent_trades(symbol=symbol, days=days),
            "decisions": self.load_agent_decisions(symbol=symbol, days=days),
        }

        with open(output_file, "w") as f:
            json.dump(export_data, f, indent=2, default=str)

        logger.info(f"Exported context to: {output_file}")
        return str(output_file)

    def cleanup_old_context(self, days: int = 90):
        """
        Cleanup old context entries

        Args:
            days: Delete entries older than this many days
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        deleted_count = 0

        for dir_path in [
            self.trade_logs_dir,
            self.backtest_dir,
            self.audit_dir,
            self.market_data_dir,
            self.agent_decisions_dir,
        ]:
            for filepath in dir_path.glob("*.json"):
                try:
                    file_time = datetime.fromtimestamp(filepath.stat().st_mtime)
                    if file_time < cutoff_date:
                        filepath.unlink()
                        deleted_count += 1
                except Exception as e:
                    logger.warning(f"Error deleting {filepath}: {e}")

        logger.info(f"Cleaned up {deleted_count} old context entries")
