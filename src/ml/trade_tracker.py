"""
Trade Tracker for Online Learning Integration
Tracks trades and triggers online learning updates.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TradeTracker:
    """
    Tracks trades and integrates with online learning system.

    This class hooks into trade execution and completion to:
    1. Track trade entry/exit states
    2. Calculate rewards using risk-adjusted reward function
    3. Trigger online learning updates
    """

    def __init__(self, online_learner=None):
        """
        Initialize trade tracker.

        Args:
            online_learner: OnlineRLLearner instance (optional)
        """
        self.online_learner = online_learner
        self.active_trades = {}  # Track active trades: {symbol: trade_info}
        self.trade_history = []
        self.save_dir = Path("data/trades")
        self.save_dir.mkdir(parents=True, exist_ok=True)

        logger.info("✅ Trade Tracker initialized")

    def on_trade_entry(
        self,
        symbol: str,
        action: int,
        entry_state: Any,
        metadata: Optional[dict[str, Any]] = None,
    ):
        """
        Called when a trade is entered.

        Args:
            symbol: Trading symbol
            action: Action taken (0=Hold, 1=Buy, 2=Sell)
            entry_state: State tensor or dict when trade was entered
            metadata: Additional metadata
        """
        trade_info = {
            "symbol": symbol,
            "action": action,
            "entry_state": entry_state,
            "entry_time": datetime.now().isoformat(),
            "metadata": metadata or {},
        }

        self.active_trades[symbol] = trade_info
        logger.debug(f"📊 Trade entry tracked: {symbol} (action: {action})")

    def on_trade_exit(
        self,
        symbol: str,
        exit_state: Any,
        trade_result: dict[str, Any],
        market_state: Optional[dict[str, Any]] = None,
    ):
        """
        Called when a trade is exited.

        Args:
            symbol: Trading symbol
            exit_state: State tensor or dict when trade was exited
            trade_result: Trade result dictionary with P/L, etc.
            market_state: Market state for reward calculation
        """
        if symbol not in self.active_trades:
            logger.warning(f"⚠️  Trade exit for {symbol} but no entry tracked")
            return

        trade_info = self.active_trades.pop(symbol)

        # Prepare complete trade record
        complete_trade = {
            **trade_info,
            "exit_state": exit_state,
            "exit_time": datetime.now().isoformat(),
            "trade_result": trade_result,
            "market_state": market_state or {},
        }

        self.trade_history.append(complete_trade)

        # Trigger online learning if available
        if self.online_learner:
            try:
                from src.ml.reward_functions import RiskAdjustedReward

                reward_calc = RiskAdjustedReward()

                self.online_learner.on_trade_complete(
                    trade_result=trade_result,
                    entry_state=trade_info["entry_state"],
                    exit_state=exit_state,
                    action=trade_info["action"],
                    reward_calculator=lambda tr, ms=None: reward_calc.calculate_from_trade_result(
                        tr, ms or market_state
                    ),
                )
                logger.info(f"🔄 Online learning updated for {symbol}")
            except Exception as e:
                logger.error(f"❌ Failed to update online learning: {e}")

        # Save trade record
        self._save_trade(complete_trade)

        logger.info(f"✅ Trade exit tracked: {symbol} (P/L: {trade_result.get('pl_pct', 0):.2%})")

    def _save_trade(self, trade: dict[str, Any]):
        """Save trade record to disk."""
        symbol = trade["symbol"]
        timestamp = trade["entry_time"].replace(":", "-").split(".")[0]
        trade_file = self.save_dir / f"{symbol}_{timestamp}.json"

        # Convert tensors to lists for JSON serialization
        trade_serializable = self._make_serializable(trade)

        with open(trade_file, "w") as f:
            json.dump(trade_serializable, f, indent=2)

    def _make_serializable(self, obj):
        """Convert tensors and non-serializable objects to JSON-compatible format."""
        import torch

        if isinstance(obj, torch.Tensor):
            return obj.cpu().numpy().tolist()
        elif isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_serializable(item) for item in obj]
        else:
            return obj

    def get_statistics(self) -> dict[str, Any]:
        """Get trade tracking statistics."""
        return {
            "active_trades": len(self.active_trades),
            "total_trades": len(self.trade_history),
            "symbols_tracked": list(self.active_trades.keys()),
        }
