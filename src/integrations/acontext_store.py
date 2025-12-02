"""
Acontext Integration - Trade Context Learning Platform

Integrates Acontext (https://github.com/memodb-io/Acontext) to enable:
1. Store: Persist trade decisions with full context
2. Observe: Track trading patterns and market conditions
3. Learn: Build skill library from successful trades

This allows the trading system to:
- Remember why specific trades were made
- Learn from successful patterns (62%+ win rate trades)
- Build reusable trading "skills" for similar market conditions
"""

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Try to import acontext - graceful fallback if not installed
try:
    from acontext import AcontextClient

    ACONTEXT_AVAILABLE = True
except ImportError:
    ACONTEXT_AVAILABLE = False
    logger.info("Acontext not installed - using local fallback storage")


@dataclass
class TradeContext:
    """Context for a single trade decision."""

    symbol: str
    action: str  # buy, sell, hold
    amount: float
    price: float
    timestamp: str

    # Decision factors
    momentum_score: float
    rsi: float
    macd_signal: str  # bullish, bearish, neutral
    volume_ratio: float

    # Market context
    market_regime: str  # bull, bear, sideways
    vix_level: float
    sector_momentum: float

    # Outcome (filled after trade closes)
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    outcome: Optional[str] = None  # win, loss, breakeven

    # Learning metadata
    pattern_tags: list[str] = None
    lessons_learned: str = None

    def __post_init__(self):
        if self.pattern_tags is None:
            self.pattern_tags = []


@dataclass
class TradingSkill:
    """A learned trading pattern/skill."""

    name: str
    description: str
    market_conditions: dict[str, Any]
    entry_rules: list[str]
    exit_rules: list[str]
    expected_win_rate: float
    avg_pnl_pct: float
    sample_size: int
    created_at: str
    last_used: str = None
    success_count: int = 0
    failure_count: int = 0


class AcontextTradeStore:
    """
    Acontext-powered trade context storage and learning.

    Features:
    - Stores every trade decision with full context
    - Learns patterns from successful trades
    - Retrieves similar past trades for decision support
    - Builds skill library for reusable strategies
    """

    def __init__(
        self,
        base_url: str = None,
        api_key: str = None,
        local_fallback_dir: str = "data/acontext_local",
    ):
        """
        Initialize Acontext store.

        Args:
            base_url: Acontext API URL (default: from env)
            api_key: API key (default: from env)
            local_fallback_dir: Directory for local storage if Acontext unavailable
        """
        self.base_url = base_url or os.getenv("ACONTEXT_BASE_URL", "http://localhost:8029/api/v1")
        self.api_key = api_key or os.getenv("ACONTEXT_API_KEY")
        self.local_dir = Path(local_fallback_dir)

        self.client = None
        self.session_id = None
        self.space_id = None

        if ACONTEXT_AVAILABLE and self.api_key:
            try:
                self.client = AcontextClient(base_url=self.base_url, api_key=self.api_key)
                logger.info("✅ Acontext client initialized")
            except Exception as e:
                logger.warning(f"Acontext client init failed: {e}, using local fallback")
                self.client = None

        # Ensure local fallback exists
        self.local_dir.mkdir(parents=True, exist_ok=True)
        (self.local_dir / "trades").mkdir(exist_ok=True)
        (self.local_dir / "skills").mkdir(exist_ok=True)

    def store_trade(self, context: TradeContext) -> str:
        """
        Store a trade decision with full context.

        Args:
            context: TradeContext with all decision factors

        Returns:
            Trade ID
        """
        trade_id = f"{context.symbol}_{context.timestamp.replace(':', '-').replace(' ', '_')}"
        trade_data = asdict(context)

        if self.client:
            try:
                # Store in Acontext
                if not self.session_id:
                    session = self.client.sessions.create()
                    self.session_id = session.id

                self.client.sessions.send_message(
                    session_id=self.session_id,
                    blob={
                        "role": "assistant",
                        "content": json.dumps(trade_data),
                        "metadata": {
                            "type": "trade_decision",
                            "symbol": context.symbol,
                            "action": context.action,
                            "trade_id": trade_id,
                        },
                    },
                    format="openai",
                )
                logger.info(f"Trade {trade_id} stored in Acontext")
            except Exception as e:
                logger.warning(f"Acontext store failed: {e}, using local")
                self._store_local(trade_id, trade_data, "trades")
        else:
            self._store_local(trade_id, trade_data, "trades")

        return trade_id

    def update_trade_outcome(
        self, trade_id: str, exit_price: float, pnl: float, pnl_pct: float, lessons: str = None
    ) -> None:
        """
        Update trade with outcome after closing.

        Args:
            trade_id: Trade ID from store_trade
            exit_price: Exit price
            pnl: Profit/loss in dollars
            pnl_pct: Profit/loss percentage
            lessons: Lessons learned from this trade
        """
        outcome = "win" if pnl > 0 else "loss" if pnl < 0 else "breakeven"

        update_data = {
            "trade_id": trade_id,
            "exit_price": exit_price,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "outcome": outcome,
            "lessons_learned": lessons,
            "closed_at": datetime.now().isoformat(),
        }

        if self.client and self.session_id:
            try:
                self.client.sessions.send_message(
                    session_id=self.session_id,
                    blob={
                        "role": "assistant",
                        "content": json.dumps(update_data),
                        "metadata": {
                            "type": "trade_outcome",
                            "trade_id": trade_id,
                            "outcome": outcome,
                        },
                    },
                    format="openai",
                )
                logger.info(f"Trade {trade_id} outcome updated: {outcome}")
            except Exception as e:
                logger.warning(f"Acontext update failed: {e}")

        # Always update local copy
        self._update_local_trade(trade_id, update_data)

    def learn_skill(
        self,
        name: str,
        description: str,
        winning_trades: list[TradeContext],
        market_conditions: dict[str, Any],
    ) -> TradingSkill:
        """
        Create a trading skill from successful trades.

        Args:
            name: Skill name (e.g., "MACD Crossover Bull Run")
            description: What this skill does
            winning_trades: List of successful trades to learn from
            market_conditions: When this skill applies

        Returns:
            TradingSkill object
        """
        if not winning_trades:
            raise ValueError("Need at least one winning trade to create skill")

        # Extract patterns from winning trades
        avg_rsi = sum(t.rsi for t in winning_trades) / len(winning_trades)
        avg_momentum = sum(t.momentum_score for t in winning_trades) / len(winning_trades)
        avg_pnl = sum(t.pnl_pct or 0 for t in winning_trades) / len(winning_trades)

        common_signals = set(winning_trades[0].pattern_tags or [])
        for t in winning_trades[1:]:
            common_signals &= set(t.pattern_tags or [])

        skill = TradingSkill(
            name=name,
            description=description,
            market_conditions=market_conditions,
            entry_rules=[
                f"RSI between {avg_rsi - 10:.0f} and {avg_rsi + 10:.0f}",
                f"Momentum score >= {avg_momentum - 5:.0f}",
                f"Market regime: {winning_trades[0].market_regime}",
            ],
            exit_rules=[
                "Exit at 5% profit target",
                "Exit at 3% stop loss",
                "Exit on MACD bearish crossover",
            ],
            expected_win_rate=len([t for t in winning_trades if (t.pnl or 0) > 0])
            / len(winning_trades),
            avg_pnl_pct=avg_pnl,
            sample_size=len(winning_trades),
            created_at=datetime.now().isoformat(),
        )

        # Store skill
        skill_data = asdict(skill)
        self._store_local(name.replace(" ", "_"), skill_data, "skills")

        if self.client:
            try:
                if not self.space_id:
                    # Create a space for trading skills
                    space = self.client.spaces.create(name="Trading Skills")
                    self.space_id = space.id

                # Store as learned experience
                self.client.spaces.experience_upsert(
                    space_id=self.space_id,
                    content=json.dumps(skill_data),
                    metadata={
                        "type": "trading_skill",
                        "name": name,
                        "win_rate": skill.expected_win_rate,
                    },
                )
                logger.info(f"Skill '{name}' stored in Acontext")
            except Exception as e:
                logger.warning(f"Acontext skill store failed: {e}")

        return skill

    def find_similar_trades(self, current_context: dict[str, Any], limit: int = 5) -> list[dict]:
        """
        Find similar past trades for decision support.

        Args:
            current_context: Current market conditions
            limit: Max trades to return

        Returns:
            List of similar past trades
        """
        if self.client and self.session_id:
            try:
                # Search Acontext
                query = f"trades with RSI near {current_context.get('rsi', 50)} and momentum {current_context.get('momentum_score', 0)}"
                results = self.client.spaces.experience_search(
                    space_id=self.space_id, query=query, mode="fast"
                )
                return results[:limit]
            except Exception as e:
                logger.warning(f"Acontext search failed: {e}")

        # Fallback to local search
        return self._search_local_trades(current_context, limit)

    def get_applicable_skills(self, market_regime: str, symbol: str = None) -> list[TradingSkill]:
        """
        Get skills applicable to current market conditions.

        Args:
            market_regime: Current market regime (bull/bear/sideways)
            symbol: Optional symbol filter

        Returns:
            List of applicable skills
        """
        skills = []
        skills_dir = self.local_dir / "skills"

        for skill_file in skills_dir.glob("*.json"):
            try:
                with open(skill_file) as f:
                    skill_data = json.load(f)

                # Check if skill applies
                skill_regime = skill_data.get("market_conditions", {}).get("regime")
                if skill_regime and skill_regime != market_regime:
                    continue

                skills.append(TradingSkill(**skill_data))
            except Exception as e:
                logger.warning(f"Failed to load skill {skill_file}: {e}")

        # Sort by win rate
        skills.sort(key=lambda s: s.expected_win_rate, reverse=True)
        return skills

    def _store_local(self, id: str, data: dict, category: str) -> None:
        """Store data locally as JSON."""
        file_path = self.local_dir / category / f"{id}.json"
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

    def _update_local_trade(self, trade_id: str, update: dict) -> None:
        """Update local trade file with outcome."""
        file_path = self.local_dir / "trades" / f"{trade_id}.json"
        if file_path.exists():
            with open(file_path) as f:
                data = json.load(f)
            data.update(update)
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2)

    def _search_local_trades(self, context: dict, limit: int) -> list[dict]:
        """Simple local trade search by similarity."""
        trades = []
        trades_dir = self.local_dir / "trades"

        target_rsi = context.get("rsi", 50)
        target_momentum = context.get("momentum_score", 0)

        for trade_file in trades_dir.glob("*.json"):
            try:
                with open(trade_file) as f:
                    trade = json.load(f)

                # Simple similarity score
                rsi_diff = abs(trade.get("rsi", 50) - target_rsi)
                momentum_diff = abs(trade.get("momentum_score", 0) - target_momentum)
                similarity = 100 - (rsi_diff + momentum_diff)

                trade["similarity_score"] = similarity
                trades.append(trade)
            except Exception as e:
                logger.debug(f"Failed to parse trade file {trade_file}: {e}")
                continue

        # Sort by similarity
        trades.sort(key=lambda t: t.get("similarity_score", 0), reverse=True)
        return trades[:limit]

    def get_stats(self) -> dict:
        """Get storage statistics."""
        trades_count = len(list((self.local_dir / "trades").glob("*.json")))
        skills_count = len(list((self.local_dir / "skills").glob("*.json")))

        return {
            "trades_stored": trades_count,
            "skills_learned": skills_count,
            "acontext_connected": self.client is not None,
            "session_active": self.session_id is not None,
        }


# Singleton instance
_store_instance = None


def get_trade_store() -> AcontextTradeStore:
    """Get the singleton trade store instance."""
    global _store_instance
    if _store_instance is None:
        _store_instance = AcontextTradeStore()
    return _store_instance


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    store = get_trade_store()

    # Example: Store a trade
    context = TradeContext(
        symbol="SPY",
        action="buy",
        amount=100.0,
        price=450.50,
        timestamp=datetime.now().isoformat(),
        momentum_score=72.5,
        rsi=45.2,
        macd_signal="bullish",
        volume_ratio=1.3,
        market_regime="bull",
        vix_level=15.2,
        sector_momentum=0.8,
        pattern_tags=["macd_crossover", "rsi_neutral", "high_volume"],
    )

    trade_id = store.store_trade(context)
    print(f"Stored trade: {trade_id}")

    # Example: Update outcome
    store.update_trade_outcome(
        trade_id=trade_id,
        exit_price=455.00,
        pnl=4.50,
        pnl_pct=1.0,
        lessons="MACD crossover in bull market with neutral RSI works well",
    )

    print(f"Stats: {store.get_stats()}")
