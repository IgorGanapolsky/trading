#!/usr/bin/env python3
"""
STATE MANAGER
Persistent memory system that survives reboots
Tracks all heuristics, profits, trades, and system state
"""

import contextlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

DATA_DIR = Path("data")
STATE_FILE = DATA_DIR / "system_state.json"
DATA_DIR.mkdir(exist_ok=True)


class StateManager:
    """
    Manages all system state with persistence
    Designed to survive reboots and provide continuity
    """

    def __init__(self):
        self.state = self.load_state()

    def load_state(self) -> dict[str, Any]:
        """Load state from disk or create new"""
        if STATE_FILE.exists():
            with open(STATE_FILE) as f:
                state = json.load(f)

            # CRITICAL: Add staleness metadata and evaluate quality
            state = self._add_staleness_metadata(state)

            # CRITICAL: Evaluate state quality and print warnings
            self._evaluate_state_quality(state)

            # BLOCK if EXPIRED (>7 days old)
            if state["meta"]["staleness_status"] == "EXPIRED":
                error_msg = f"""
╔════════════════════════════════════════════════════════════════╗
║  CRITICAL ERROR: STATE DATA EXPIRED                            ║
╚════════════════════════════════════════════════════════════════╝

State last updated: {state["meta"]["last_updated"]}
Staleness: {state["meta"]["staleness_hours"]:.1f} hours ({state["meta"]["staleness_hours"] / 24:.1f} days)
Status: {state["meta"]["staleness_status"]}

⛔ REFUSING TO LOAD EXPIRED DATA ⛔

This prevents hallucinations where the system reports old data as current.

ACTION REQUIRED:
1. Run daily_checkin.py to refresh state with current data
2. Or manually update system_state.json with current account data
"""
                raise ValueError(error_msg)

            return state
        return self._create_initial_state()

    def save_state(self):
        """Persist state to disk"""
        self.state["meta"]["last_updated"] = datetime.now().isoformat()

        # Clear staleness metadata when saving fresh data
        if "last_loaded" in self.state["meta"]:
            del self.state["meta"]["last_loaded"]
        if "staleness_hours" in self.state["meta"]:
            del self.state["meta"]["staleness_hours"]
        if "staleness_status" in self.state["meta"]:
            del self.state["meta"]["staleness_status"]
        if "self_evaluation" in self.state["meta"]:
            del self.state["meta"]["self_evaluation"]

        with open(STATE_FILE, "w") as f:
            json.dump(self.state, f, indent=2)

    def _create_initial_state(self) -> dict[str, Any]:
        """Create initial state structure"""
        return {
            "meta": {
                "version": "1.0",
                "created": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
            },
            "challenge": {
                "start_date": date.today().isoformat(),
                "current_day": 1,
                "total_days": 30,
                "status": "active",
            },
            "account": {
                "starting_balance": 100000.0,
                "current_equity": 100000.0,
                "cash": 100000.0,
                "positions_value": 0.0,
                "total_pl": 0.0,
                "total_pl_pct": 0.0,
            },
            "investments": {
                "total_invested": 0.0,
                "tier1_invested": 0.0,
                "tier2_invested": 0.0,
                "tier3_reserve": 0.0,
                "tier4_reserve": 0.0,
            },
            "performance": {
                "total_trades": 0,
                "closed_trades": [],  # List of closed trades with realized P/L
                "open_positions": [],  # List of open positions with unrealized P/L
                "winning_trades": 0,  # Count of closed winning trades
                "losing_trades": 0,  # Count of closed losing trades
                "win_rate": 0.0,  # Win rate based on closed trades only
                "best_trade": None,
                "worst_trade": None,
                "avg_return": 0.0,
            },
            "strategies": {
                "tier1": {
                    "name": "Core ETF Strategy",
                    "allocation": 0.67,
                    "daily_amount": 10.0,
                    "trades_executed": 0,
                    "total_invested": 0.0,
                    "status": "active",
                },
                "tier2": {
                    "name": "Growth Stock Strategy",
                    "allocation": 0.33,
                    "daily_amount": 5.0,
                    "trades_executed": 0,
                    "total_invested": 0.0,
                    "status": "active",
                },
                "tier3": {
                    "name": "IPO Strategy",
                    "allocation": 0.1,
                    "daily_amount": 1.0,
                    "reserve_balance": 0.0,
                    "status": "tracking",
                },
                "tier4": {
                    "name": "Crowdfunding Strategy",
                    "allocation": 0.1,
                    "daily_amount": 1.0,
                    "reserve_balance": 0.0,
                    "status": "tracking",
                },
            },
            "heuristics": {
                "best_performing_etf": None,
                "best_performing_stock": None,
                "avg_daily_return": 0.0,
                "max_drawdown": 0.0,
                "sharpe_ratio": 0.0,
                "volatility": 0.0,
                "winning_symbols": [],
                "losing_symbols": [],
            },
            "automation": {
                "cron_enabled": False,
                "last_execution": None,
                "next_execution": None,
                "execution_count": 0,
                "failures": 0,
            },
            "video_analysis": {
                "enabled": True,
                "videos_analyzed": 0,
                "stocks_added_from_videos": 0,
                "last_analysis_date": None,
                "video_sources": [],
                "watchlist_additions": [],
            },
            "notes": [],
        }

    def update_challenge_day(self):
        """Update current day of challenge"""
        start = datetime.fromisoformat(self.state["challenge"]["start_date"]).date()
        today = date.today()
        day = (today - start).days + 1
        self.state["challenge"]["current_day"] = day
        self.save_state()

    def record_trade(
        self,
        tier: str,
        symbol: str,
        amount: float,
        order_id: str,
        attribution_metadata: Optional[dict[str, Any]] = None,
    ):
        """Record a trade execution (opening a position) with attribution metadata"""
        # Update strategy stats
        if tier in ["tier1", "tier2"]:
            self.state["strategies"][tier]["trades_executed"] += 1
            self.state["strategies"][tier]["total_invested"] += amount

        # Update investments
        self.state["investments"]["total_invested"] += amount
        if tier == "tier1":
            self.state["investments"]["tier1_invested"] += amount
        elif tier == "tier2":
            self.state["investments"]["tier2_invested"] += amount

        # Update performance
        self.state["performance"]["total_trades"] += 1

        # Add to open positions (will be moved to closed_trades when position closes)
        if "open_positions" not in self.state["performance"]:
            self.state["performance"]["open_positions"] = []

        position_data = {
            "tier": tier,
            "symbol": symbol,
            "amount": amount,
            "order_id": order_id,
            "entry_date": datetime.now().isoformat(),
            "entry_price": None,  # Will be updated when we get fill price
        }

        # Store attribution metadata for performance analysis
        if attribution_metadata:
            position_data["attribution_metadata"] = attribution_metadata

        self.state["performance"]["open_positions"].append(position_data)

        # Add note
        self.add_note(f"Trade executed: {tier.upper()} - {symbol} ${amount}")

        self.save_state()

    def record_closed_trade(
        self,
        symbol: str,
        entry_price: float,
        exit_price: float,
        quantity: float,
        entry_date: str,
        exit_date: str = None,
    ):
        """
        Record a closed trade with realized P/L.

        Args:
            symbol: Stock symbol
            entry_price: Price when position was opened
            exit_price: Price when position was closed
            quantity: Number of shares
            entry_date: Date position was opened
            exit_date: Date position was closed (defaults to now)
        """
        if exit_date is None:
            exit_date = datetime.now().isoformat()

        # Calculate realized P/L
        pl = (exit_price - entry_price) * quantity
        pl_pct = ((exit_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0

        # Find and remove from open_positions
        if "open_positions" not in self.state["performance"]:
            self.state["performance"]["open_positions"] = []
        if "closed_trades" not in self.state["performance"]:
            self.state["performance"]["closed_trades"] = []

        # Remove from open positions (find matching symbol)
        open_positions = self.state["performance"]["open_positions"]
        matching_position = None
        for pos in open_positions:
            if pos.get("symbol") == symbol:
                matching_position = pos
                open_positions.remove(pos)
                break

        # Add to closed trades
        closed_trade = {
            "symbol": symbol,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "quantity": quantity,
            "entry_date": entry_date,
            "exit_date": exit_date,
            "pl": pl,
            "pl_pct": pl_pct,
            "tier": matching_position.get("tier") if matching_position else "unknown",
        }

        # Preserve attribution metadata from original position
        if matching_position and "attribution_metadata" in matching_position:
            closed_trade["attribution_metadata"] = matching_position["attribution_metadata"]

        self.state["performance"]["closed_trades"].append(closed_trade)

        # Update win/loss counts
        if pl > 0:
            self.state["performance"]["winning_trades"] += 1
        elif pl < 0:
            self.state["performance"]["losing_trades"] += 1

        # Recalculate win rate based on closed trades only
        total_closed = len(self.state["performance"]["closed_trades"])
        if total_closed > 0:
            self.state["performance"]["win_rate"] = (
                self.state["performance"]["winning_trades"] / total_closed * 100
            )
        else:
            self.state["performance"]["win_rate"] = 0.0

        # Update best/worst trade
        if not self.state["performance"]["best_trade"] or pl > self.state["performance"][
            "best_trade"
        ].get("pl", -float("inf")):
            self.state["performance"]["best_trade"] = {
                "symbol": symbol,
                "pl": pl,
                "pl_pct": pl_pct,
            }
        if not self.state["performance"]["worst_trade"] or pl < self.state["performance"][
            "worst_trade"
        ].get("pl", float("inf")):
            self.state["performance"]["worst_trade"] = {
                "symbol": symbol,
                "pl": pl,
                "pl_pct": pl_pct,
            }

        # Calculate average return
        if total_closed > 0:
            total_return = sum(t["pl_pct"] for t in self.state["performance"]["closed_trades"])
            self.state["performance"]["avg_return"] = total_return / total_closed

        self.add_note(
            f"Position closed: {symbol} - Entry: ${entry_price:.2f}, Exit: ${exit_price:.2f}, P/L: ${pl:.2f} ({pl_pct:+.2f}%)"
        )
        self.save_state()

    def update_open_positions(self, positions: list):
        """
        Update open positions with current unrealized P/L.

        Args:
            positions: List of position dicts with symbol, qty, entry_price, current_price, etc.
        """
        if "open_positions" not in self.state["performance"]:
            self.state["performance"]["open_positions"] = []

        # Update existing open positions with current prices
        for pos_data in positions:
            symbol = pos_data.get("symbol")
            current_price = pos_data.get("current_price")
            entry_price = pos_data.get("entry_price")
            qty = pos_data.get("qty", 0)

            if not symbol or not current_price or not entry_price:
                continue

            # Find matching open position
            for open_pos in self.state["performance"]["open_positions"]:
                if open_pos.get("symbol") == symbol:
                    # Update with current price and unrealized P/L
                    open_pos["current_price"] = current_price
                    open_pos["unrealized_pl"] = (current_price - entry_price) * qty
                    open_pos["unrealized_pl_pct"] = (
                        ((current_price - entry_price) / entry_price * 100)
                        if entry_price > 0
                        else 0
                    )
                    open_pos["last_updated"] = datetime.now().isoformat()
                    break

        self.save_state()

    def update_account(self, equity: float, cash: float, pl: float, pl_pct: float):
        """Update account information"""
        self.state["account"]["current_equity"] = equity
        self.state["account"]["cash"] = cash
        self.state["account"]["positions_value"] = equity - cash
        self.state["account"]["total_pl"] = pl
        self.state["account"]["total_pl_pct"] = pl_pct
        self.save_state()

    def update_heuristics(self, **kwargs):
        """Update heuristic data"""
        for key, value in kwargs.items():
            if key in self.state["heuristics"]:
                self.state["heuristics"][key] = value
        self.save_state()

    def add_note(self, note: str):
        """Add a note to system log"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.state["notes"].append(f"[{timestamp}] {note}")
        # Keep last 100 notes
        if len(self.state["notes"]) > 100:
            self.state["notes"] = self.state["notes"][-100:]
        self.save_state()

    def record_video_analysis(self, video_title: str, analyst: str, stocks_added: list[str]):
        """Record a YouTube video analysis"""
        if "video_analysis" not in self.state:
            self.state["video_analysis"] = {
                "enabled": True,
                "videos_analyzed": 0,
                "stocks_added_from_videos": 0,
                "last_analysis_date": None,
                "video_sources": [],
                "watchlist_additions": [],
            }

        self.state["video_analysis"]["videos_analyzed"] += 1
        self.state["video_analysis"]["stocks_added_from_videos"] += len(stocks_added)
        self.state["video_analysis"]["last_analysis_date"] = datetime.now().isoformat()

        # Add to video sources (keep last 20)
        video_entry = {
            "title": video_title,
            "analyst": analyst,
            "date": datetime.now().isoformat(),
            "stocks_added": stocks_added,
        }
        self.state["video_analysis"]["video_sources"].append(video_entry)
        if len(self.state["video_analysis"]["video_sources"]) > 20:
            self.state["video_analysis"]["video_sources"] = self.state["video_analysis"][
                "video_sources"
            ][-20:]

        # Add to watchlist additions
        for ticker in stocks_added:
            self.state["video_analysis"]["watchlist_additions"].append(
                {
                    "ticker": ticker,
                    "source": f"{analyst} - {video_title}",
                    "date_added": datetime.now().isoformat(),
                }
            )

        self.add_note(f"Video analysis: {analyst} - {len(stocks_added)} stocks added to watchlist")
        self.save_state()

    def get_summary(self) -> dict[str, Any]:
        """Get current state summary"""
        return {
            "day": self.state["challenge"]["current_day"],
            "equity": self.state["account"]["current_equity"],
            "pl": self.state["account"]["total_pl"],
            "pl_pct": self.state["account"]["total_pl_pct"],
            "trades": self.state["performance"]["total_trades"],
            "invested": self.state["investments"]["total_invested"],
        }

    def _add_staleness_metadata(self, state: dict[str, Any]) -> dict[str, Any]:
        """Add staleness metadata to state"""
        now = datetime.now()
        last_updated = datetime.fromisoformat(state["meta"]["last_updated"])

        staleness_hours = (now - last_updated).total_seconds() / 3600

        # Determine staleness status
        # STRICT thresholds to prevent hallucinations
        if staleness_hours < 24:
            status = "FRESH"
        elif staleness_hours < 48:
            status = "AGING"
        elif staleness_hours < 72:  # 3 days
            status = "STALE"
        else:  # >3 days
            status = "EXPIRED"

        state["meta"]["last_loaded"] = now.isoformat()
        state["meta"]["staleness_hours"] = staleness_hours
        state["meta"]["staleness_status"] = status

        return state

    def _evaluate_state_quality(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        Self-evaluate state quality and staleness
        PRINTS WARNINGS to console
        Returns evaluation dict
        """
        warnings = []
        recommendations = []

        staleness_hours = state["meta"]["staleness_hours"]
        staleness_days = staleness_hours / 24
        status = state["meta"]["staleness_status"]

        # Generate warnings based on staleness
        if status == "FRESH":
            confidence = 0.95
        elif status == "AGING":
            confidence = 0.70
            warnings.append(
                f"State is {staleness_days:.1f} days old - account balance may not reflect recent trades"
            )
            recommendations.append("Run daily_checkin.py to refresh state")
        elif status == "STALE":
            confidence = 0.30
            warnings.append(
                f"State is {staleness_days:.1f} days old - HIGH RISK of using stale data"
            )
            warnings.append(
                "Account balance not updated in several days - may not reflect current positions"
            )
            recommendations.append("URGENT: Run daily_checkin.py to refresh state")
        else:  # EXPIRED
            confidence = 0.05
            warnings.append(f"State is {staleness_days:.1f} days old - CRITICAL STALENESS")
            warnings.append("Data is severely outdated and CANNOT be trusted")
            warnings.append("Using this data WILL cause hallucinations")
            recommendations.append("REQUIRED: Run daily_checkin.py immediately")

        # Check if challenge day calculation would be wrong
        if staleness_days >= 1:
            warnings.append(f"Challenge day calculation may be off by {int(staleness_days)} days")

        evaluation = {
            "warnings": warnings,
            "recommendations": recommendations,
            "confidence_in_state": confidence,
            "staleness_hours": staleness_hours,
            "staleness_days": staleness_days,
            "status": status,
        }

        state["meta"]["self_evaluation"] = evaluation

        # PRINT WARNINGS TO CONSOLE
        if status != "FRESH":
            print("\n" + "=" * 70)
            print(f"⚠️  SYSTEM STATE WARNINGS ⚠️  [{status}]")
            print("=" * 70)
            for warning in warnings:
                print(f"  ⚠️  {warning}")
            print()
            print("RECOMMENDATIONS:")
            for rec in recommendations:
                print(f"  → {rec}")
            print()
            print(f"Confidence in state: {confidence * 100:.0f}% ", end="")
            if confidence < 0.3:
                print("(VERY LOW)")
            elif confidence < 0.7:
                print("(LOW)")
            else:
                print("(MODERATE)")
            print("=" * 70)
            print()

        return evaluation

    def check_trade_staleness(self) -> dict[str, Any]:
        """
        Check if last trade was too long ago - detects silent automation failures.

        Returns:
            Dictionary with:
            - status: "OK", "WARNING", or "ERROR"
            - message: Description of the issue
            - last_trade_date: ISO date string of last trade
            - hours_since_last_trade: Hours since last trade
            - recommended_action: What to do about it
        """
        from datetime import datetime

        # Get last trade date from performance
        last_trade_date = None

        # Check for most recent trade in notes
        for note in reversed(self.state.get("notes", [])):
            if "Trade executed:" in note or "order executed" in note:
                # Extract timestamp from note format: [2025-11-07 14:01]
                try:
                    timestamp_str = note.split("]")[0].strip("[")
                    last_trade_date = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M")
                    break
                except (ValueError, IndexError):
                    continue

        # If no trade found in notes, check automation metadata
        if not last_trade_date and "automation" in self.state:
            last_exec = self.state["automation"].get("last_successful_execution")
            if last_exec:
                with contextlib.suppress(ValueError, TypeError):
                    last_trade_date = datetime.fromisoformat(last_exec)

        # No trades found at all
        if not last_trade_date:
            return {
                "status": "WARNING",
                "message": "No trades found in system history",
                "last_trade_date": None,
                "hours_since_last_trade": None,
                "recommended_action": "Check if system has ever executed trades successfully",
            }

        # Calculate hours since last trade
        now = datetime.now()
        hours_since = (now - last_trade_date).total_seconds() / 3600

        # Check if it's a weekday (Monday=0, Friday=4)
        is_weekday = now.weekday() < 5

        # Determine status based on time since last trade
        if hours_since > 120:  # 5 days
            status = "ERROR"
            message = (
                f"CRITICAL: No trades for {hours_since / 24:.1f} days - automation likely broken"
            )
            action = "URGENT: Check GitHub Actions workflow and system logs immediately"
        elif hours_since > 48:  # 2 days
            status = "ERROR"
            message = (
                f"No trades for {hours_since / 24:.1f} days on weekday - automation may be broken"
            )
            action = "Check GitHub Actions workflow status and logs"
        elif is_weekday and hours_since > 24:
            status = "WARNING"
            message = f"No trades for {hours_since:.1f} hours on weekday - check automation"
            action = "Verify GitHub Actions workflow is running daily at 9:35 AM ET"
        else:
            status = "OK"
            message = f"Last trade {hours_since:.1f} hours ago - normal"
            action = None

        return {
            "status": status,
            "message": message,
            "last_trade_date": last_trade_date.isoformat(),
            "hours_since_last_trade": hours_since,
            "recommended_action": action,
        }

    def export_for_context(self) -> str:
        """Export state as context for Claude memory"""
        summary = self.get_summary()

        # Include staleness warning in context
        staleness_warning = ""
        if "self_evaluation" in self.state["meta"]:
            eval_data = self.state["meta"]["self_evaluation"]
            if eval_data["status"] != "FRESH":
                staleness_warning = f"""
⚠️  DATA STALENESS WARNING ⚠️
Status: {eval_data["status"]}
Age: {eval_data["staleness_days"]:.1f} days
Confidence: {eval_data["confidence_in_state"] * 100:.0f}%
Warnings: {len(eval_data["warnings"])} issues detected
"""

        context = f"""
TRADING SYSTEM STATE (Day {summary["day"]}/30)
{staleness_warning}
ACCOUNT:
- Equity: ${summary["equity"]:,.2f}
- P/L: ${summary["pl"]:+,.2f} ({summary["pl_pct"]:+.2f}%)
- Total Invested: ${summary["invested"]:.2f}
- Total Trades: {summary["trades"]}

STRATEGIES:
- Tier 1 (Core ETF): {self.state["strategies"]["tier1"]["trades_executed"]} trades
- Tier 2 (Growth): {self.state["strategies"]["tier2"]["trades_executed"]} trades
- Tier 3 (IPO): ${self.state["strategies"]["tier3"]["reserve_balance"]:.2f} reserved
- Tier 4 (Crowdfunding): ${self.state["strategies"]["tier4"]["reserve_balance"]:.2f} reserved

HEURISTICS:
- Best ETF: {self.state["heuristics"]["best_performing_etf"]}
- Avg Daily Return: {self.state["heuristics"]["avg_daily_return"]:.2f}%
- Max Drawdown: {self.state["heuristics"]["max_drawdown"]:.2f}%

RECENT NOTES:
{chr(10).join(self.state["notes"][-5:])}
"""
        return context


def main():
    """Test state manager"""
    sm = StateManager()

    print("=== SYSTEM STATE ===")
    print(json.dumps(sm.get_summary(), indent=2))

    print("\n=== CONTEXT FOR CLAUDE ===")
    print(sm.export_for_context())


if __name__ == "__main__":
    main()
