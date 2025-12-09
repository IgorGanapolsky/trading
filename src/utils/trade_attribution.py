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
from typing import Any

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
        indicators: dict[str, float] | None = None,
        strategy: str | None = None,
        tier: str | None = None,
        gates_approved: dict[str, dict[str, Any]] | None = None,
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
            gates_approved: Dict of gates that approved this trade with their metrics
                Example: {
                    "momentum": {"score": 0.72, "signal": "buy"},
                    "rl": {"confidence": 0.65, "action": "long"},
                    "llm_sentiment": {"score": 0.3, "source": "bias_store"},
                    "introspection": {"confidence": 0.8, "state": "INFORMED_GUESS"},
                    "risk": {"position_size": 500, "atr_stop": 145.50}
                }

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
            "gates_approved": gates_approved or {},
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
        lessons_learned: str | None = None,
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

    def get_pnl_by_gate(self) -> dict[str, dict[str, float]]:
        """
        Analyze P/L attribution by gate to identify which gates add value.

        Returns:
            Dict mapping gate name to performance metrics:
            {
                "momentum": {"total_pnl": 150.0, "trades": 10, "avg_pnl": 15.0, "win_rate": 0.6},
                "rl": {"total_pnl": 120.0, "trades": 8, "avg_pnl": 15.0, "win_rate": 0.625},
                ...
            }
        """
        complete_trades = list(self.attribution_dir.glob("*_complete.json"))

        if not complete_trades:
            return {}

        # Track metrics per gate
        gate_metrics: dict[str, dict[str, Any]] = {}

        for trade_file in complete_trades:
            with open(trade_file) as f:
                trade = json.load(f)

            gates_approved = trade.get("gates_approved", {})
            exit_data = trade.get("exit", {})
            pl = exit_data.get("pl", 0.0)

            for gate_name, gate_data in gates_approved.items():
                if gate_name not in gate_metrics:
                    gate_metrics[gate_name] = {
                        "total_pnl": 0.0,
                        "trades": 0,
                        "wins": 0,
                        "losses": 0,
                        "pnl_list": [],
                    }

                gate_metrics[gate_name]["total_pnl"] += pl
                gate_metrics[gate_name]["trades"] += 1
                gate_metrics[gate_name]["pnl_list"].append(pl)

                if pl > 0:
                    gate_metrics[gate_name]["wins"] += 1
                else:
                    gate_metrics[gate_name]["losses"] += 1

        # Calculate summary stats
        result = {}
        for gate_name, metrics in gate_metrics.items():
            trades = metrics["trades"]
            wins = metrics["wins"]
            pnl_list = metrics["pnl_list"]

            result[gate_name] = {
                "total_pnl": metrics["total_pnl"],
                "trades": trades,
                "avg_pnl": metrics["total_pnl"] / trades if trades > 0 else 0.0,
                "win_rate": wins / trades if trades > 0 else 0.0,
                "max_win": max(pnl_list) if pnl_list else 0.0,
                "max_loss": min(pnl_list) if pnl_list else 0.0,
            }

        return result

    def generate_gate_contribution_report(self) -> str:
        """Generate a markdown report of gate contributions to P/L."""
        gate_pnl = self.get_pnl_by_gate()
        summary = self.get_trade_attribution_summary()

        lines = [
            "# Trade Attribution Report",
            "",
            f"**Total Trades**: {summary['total_trades']}",
            f"**Hypothesis Match Rate**: {summary['hypothesis_match_rate']:.1%}",
            "",
            "## P/L by Gate",
            "",
            "| Gate | Total P/L | Trades | Avg P/L | Win Rate |",
            "|------|-----------|--------|---------|----------|",
        ]

        # Sort by total P/L descending
        sorted_gates = sorted(gate_pnl.items(), key=lambda x: x[1]["total_pnl"], reverse=True)

        for gate_name, metrics in sorted_gates:
            lines.append(
                f"| {gate_name} | ${metrics['total_pnl']:+.2f} | {metrics['trades']} | "
                f"${metrics['avg_pnl']:+.2f} | {metrics['win_rate']:.1%} |"
            )

        lines.extend([
            "",
            "## By Entry Reason",
            "",
        ])
        for reason, count in summary["by_entry_reason"].items():
            lines.append(f"- {reason}: {count} trades")

        lines.extend([
            "",
            "## By Exit Reason",
            "",
        ])
        for reason, count in summary["by_exit_reason"].items():
            lines.append(f"- {reason}: {count} trades")

        lines.extend([
            "",
            "## By Market Regime",
            "",
        ])
        for regime, count in summary["by_regime"].items():
            lines.append(f"- {regime}: {count} trades")

        return "\n".join(lines)


# ruff: noqa: UP045
