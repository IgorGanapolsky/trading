"""
Trade Attribution Logger

Logs comprehensive trade-level attribution including:
- Entry reason (why we entered)
- Exit reason (why we exited)
- Market regime (at entry and exit)
- Hypothesis (what we expected)
- Actual outcome vs hypothesis
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TradeAttributionLogger:
    """Logs trade-level attribution for analysis and learning."""

    def __init__(self, data_dir: Path = Path("data")):
        self.data_dir = data_dir
        self.attribution_dir = data_dir / "trade_attribution"
        self.attribution_dir.mkdir(parents=True, exist_ok=True)

    def log_trade_entry(
        self,
        symbol: str,
        entry_price: float,
        quantity: float,
        entry_reason: str,
        market_regime: str,
        hypothesis: str,
        indicators: Optional[dict[str, float]] = None,
        strategy: Optional[str] = None,
        tier: Optional[str] = None,
    ) -> str:
        """
        Log trade entry with full attribution.

        Args:
            symbol: Trading symbol
            entry_price: Entry price
            quantity: Quantity purchased
            entry_reason: Why we entered (e.g., "MACD bullish crossover", "RSI oversold")
            market_regime: Market regime at entry (e.g., "BULL", "BEAR", "SIDEWAYS")
            hypothesis: What we expect to happen (e.g., "Price will rise 2% in 5 days")
            indicators: Technical indicators at entry
            strategy: Strategy name
            tier: Tier (T1_CORE, T2_GROWTH, etc.)

        Returns:
            Trade ID for tracking
        """
        trade_id = f"{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        entry_data = {
            "trade_id": trade_id,
            "symbol": symbol,
            "entry": {
                "timestamp": datetime.now().isoformat(),
                "price": entry_price,
                "quantity": quantity,
                "value": entry_price * quantity,
                "reason": entry_reason,
                "market_regime": market_regime,
                "hypothesis": hypothesis,
                "indicators": indicators or {},
                "strategy": strategy,
                "tier": tier,
            },
            "status": "open",
        }

        # Save to file
        filepath = self.attribution_dir / f"{trade_id}_entry.json"
        with open(filepath, "w") as f:
            json.dump(entry_data, f, indent=2)

        logger.info(
            f"📊 Trade entry logged: {symbol} @ ${entry_price:.2f} | "
            f"Reason: {entry_reason} | Hypothesis: {hypothesis}"
        )

        return trade_id

    def log_trade_exit(
        self,
        trade_id: str,
        exit_price: float,
        exit_reason: str,
        market_regime: str,
        pl: float,
        pl_pct: float,
        actual_outcome: str,
        hypothesis_match: bool,
        lessons_learned: Optional[str] = None,
    ) -> None:
        """
        Log trade exit with outcome analysis.

        Args:
            trade_id: Trade ID from entry log
            exit_price: Exit price
            exit_reason: Why we exited (e.g., "Stop loss hit", "Take profit", "Time-based")
            market_regime: Market regime at exit
            pl: Profit/loss in dollars
            pl_pct: Profit/loss percentage
            actual_outcome: What actually happened vs hypothesis
            hypothesis_match: Whether hypothesis matched actual outcome
            lessons_learned: Key learnings from this trade
        """
        # Load entry data
        entry_file = self.attribution_dir / f"{trade_id}_entry.json"
        if not entry_file.exists():
            logger.warning(f"Entry file not found for trade_id: {trade_id}")
            return

        with open(entry_file) as f:
            trade_data = json.load(f)

        # Add exit data
        trade_data["exit"] = {
            "timestamp": datetime.now().isoformat(),
            "price": exit_price,
            "reason": exit_reason,
            "market_regime": market_regime,
            "pl": pl,
            "pl_pct": pl_pct,
            "actual_outcome": actual_outcome,
            "hypothesis_match": hypothesis_match,
            "lessons_learned": lessons_learned,
        }

        # Calculate entry-exit analysis
        entry_price = trade_data["entry"]["price"]
        price_change_pct = ((exit_price - entry_price) / entry_price) * 100

        trade_data["analysis"] = {
            "price_change_pct": price_change_pct,
            "hypothesis_match": hypothesis_match,
            "entry_regime": trade_data["entry"]["market_regime"],
            "exit_regime": market_regime,
            "regime_change": market_regime != trade_data["entry"]["market_regime"],
        }

        trade_data["status"] = "closed"

        # Save complete trade
        complete_file = self.attribution_dir / f"{trade_id}_complete.json"
        with open(complete_file, "w") as f:
            json.dump(trade_data, f, indent=2)

        logger.info(
            f"✅ Trade exit logged: {trade_id} | P/L: ${pl:+.2f} ({pl_pct:+.2f}%) | "
            f"Hypothesis match: {hypothesis_match} | Outcome: {actual_outcome}"
        )

    def get_trade_attribution_summary(self) -> dict[str, Any]:
        """Get summary of all trade attributions."""
        complete_trades = list(self.attribution_dir.glob("*_complete.json"))

        if not complete_trades:
            return {
                "total_trades": 0,
                "hypothesis_match_rate": 0.0,
                "by_entry_reason": {},
                "by_exit_reason": {},
                "by_regime": {},
            }

        hypothesis_matches = 0
        by_entry_reason = {}
        by_exit_reason = {}
        by_regime = {}

        for trade_file in complete_trades:
            with open(trade_file) as f:
                trade = json.load(f)

            if trade.get("analysis", {}).get("hypothesis_match"):
                hypothesis_matches += 1

            entry_reason = trade["entry"]["reason"]
            by_entry_reason[entry_reason] = by_entry_reason.get(entry_reason, 0) + 1

            exit_reason = trade["exit"]["reason"]
            by_exit_reason[exit_reason] = by_exit_reason.get(exit_reason, 0) + 1

            regime = trade["entry"]["market_regime"]
            by_regime[regime] = by_regime.get(regime, 0) + 1

        return {
            "total_trades": len(complete_trades),
            "hypothesis_match_rate": (
                hypothesis_matches / len(complete_trades) if complete_trades else 0.0
            ),
            "by_entry_reason": by_entry_reason,
            "by_exit_reason": by_exit_reason,
            "by_regime": by_regime,
        }
