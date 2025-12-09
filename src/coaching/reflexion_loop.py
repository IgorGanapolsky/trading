"""
Reflexion Loop - Self-Improving Trading Agent

Based on the Reflexion framework (Shinn et al. 2023) that shows:
- Self-reflection significantly improves LLM agent performance
- Storing reflections in memory enables rapid learning
- Most effective on difficult tasks (like trading)

This module implements:
- Post-trade reflection generation
- Reflection memory storage
- Reflection injection into future decisions
- Pattern recognition across trades

Key insight: The system learns from mistakes by explicitly reflecting
on what went wrong and storing those learnings for future use.
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default path for reflection memory
REFLECTION_MEMORY_PATH = Path("data/reflexion_memory.json")


@dataclass
class TradeReflection:
    """A reflection on a completed trade."""

    trade_id: str
    symbol: str
    timestamp: str
    action: str  # BUY/SELL
    entry_price: float
    exit_price: float | None
    pnl: float
    pnl_pct: float
    is_win: bool

    # Pre-trade context
    pre_trade_signals: dict[str, Any]
    pre_trade_confidence: float
    pre_trade_reasoning: str

    # Post-trade reflection
    what_worked: list[str]
    what_failed: list[str]
    lesson_learned: str
    would_take_again: bool
    improvement_action: str

    # Patterns identified
    pattern_tags: list[str]  # e.g., ["fomo", "good_entry", "early_exit"]


@dataclass
class ReflectionMemory:
    """Long-term memory of trade reflections."""

    reflections: list[TradeReflection]
    total_trades: int
    win_rate: float
    common_mistakes: list[str]
    best_patterns: list[str]
    last_updated: str


class ReflexionLoop:
    """
    Reflexion Loop: Self-improving trading agent through reflection.

    Key components:
    1. reflect_on_trade(): Generate reflection after each trade
    2. store_reflection(): Save to long-term memory
    3. get_relevant_reflections(): Retrieve past learnings for context
    4. generate_reflection_context(): Format for LLM prompt injection

    Usage:
        loop = ReflexionLoop()

        # After each trade completes:
        reflection = loop.reflect_on_trade(trade_data)
        loop.store_reflection(reflection)

        # Before making new trade decisions:
        context = loop.generate_reflection_context(symbol)
        # Inject context into LLM prompts
    """

    def __init__(self, memory_path: Path | str | None = None):
        self.memory_path = Path(memory_path) if memory_path else REFLECTION_MEMORY_PATH
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        self.memory = self._load_memory()

    def _load_memory(self) -> ReflectionMemory:
        """Load reflection memory from disk."""
        if self.memory_path.exists():
            try:
                with self.memory_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    reflections = [
                        TradeReflection(**r) for r in data.get("reflections", [])
                    ]
                    return ReflectionMemory(
                        reflections=reflections,
                        total_trades=data.get("total_trades", 0),
                        win_rate=data.get("win_rate", 0.0),
                        common_mistakes=data.get("common_mistakes", []),
                        best_patterns=data.get("best_patterns", []),
                        last_updated=data.get("last_updated", ""),
                    )
            except Exception as e:
                logger.warning(f"Failed to load reflection memory: {e}")

        return ReflectionMemory(
            reflections=[],
            total_trades=0,
            win_rate=0.0,
            common_mistakes=[],
            best_patterns=[],
            last_updated=datetime.now(timezone.utc).isoformat(),
        )

    def _save_memory(self) -> None:
        """Save reflection memory to disk."""
        try:
            data = {
                "reflections": [asdict(r) for r in self.memory.reflections[-100:]],  # Keep last 100
                "total_trades": self.memory.total_trades,
                "win_rate": self.memory.win_rate,
                "common_mistakes": self.memory.common_mistakes,
                "best_patterns": self.memory.best_patterns,
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }
            with self.memory_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save reflection memory: {e}")

    def reflect_on_trade(
        self,
        trade_id: str,
        symbol: str,
        action: str,
        entry_price: float,
        exit_price: float | None,
        pnl: float,
        pre_trade_signals: dict[str, Any],
        pre_trade_confidence: float,
        pre_trade_reasoning: str,
    ) -> TradeReflection:
        """
        Generate a reflection on a completed trade.

        This is where the system learns. It analyzes:
        - What signals were present before the trade
        - What the outcome was
        - What worked and what didn't
        - What lesson to take forward

        Args:
            trade_id: Unique identifier for the trade
            symbol: Stock ticker
            action: BUY or SELL
            entry_price: Price at entry
            exit_price: Price at exit (or None if still open)
            pnl: Profit/loss in dollars
            pre_trade_signals: Technical signals at entry
            pre_trade_confidence: Model confidence at entry
            pre_trade_reasoning: Why the trade was taken

        Returns:
            TradeReflection with analysis and lessons
        """
        # Calculate P/L percentage
        pnl_pct = (pnl / (entry_price * 1)) * 100 if entry_price > 0 else 0
        is_win = pnl > 0

        # Analyze what worked and what failed
        what_worked = []
        what_failed = []
        pattern_tags = []

        # Signal analysis
        rsi = pre_trade_signals.get("rsi", 50)
        macd_hist = pre_trade_signals.get("macd_histogram", 0)
        volume_ratio = pre_trade_signals.get("volume_ratio", 1.0)

        if is_win:
            # Winning trade - identify what worked
            if action == "BUY":
                if rsi < 40:
                    what_worked.append("Bought on RSI weakness - mean reversion worked")
                    pattern_tags.append("rsi_reversal")
                if macd_hist > 0:
                    what_worked.append("MACD momentum confirmed direction")
                    pattern_tags.append("macd_confirmed")
                if volume_ratio > 1.2:
                    what_worked.append("High volume validated the move")
                    pattern_tags.append("volume_confirmed")
            if pre_trade_confidence > 0.7:
                what_worked.append(f"High confidence ({pre_trade_confidence:.0%}) was justified")
                pattern_tags.append("high_confidence_win")
        else:
            # Losing trade - identify what failed
            if action == "BUY":
                if rsi > 60:
                    what_failed.append("Bought at elevated RSI - chased the move")
                    pattern_tags.append("chased_entry")
                if macd_hist < 0:
                    what_failed.append("MACD was negative - fought momentum")
                    pattern_tags.append("fought_momentum")
                if volume_ratio < 0.8:
                    what_failed.append("Low volume - move lacked conviction")
                    pattern_tags.append("low_volume_entry")
            if pre_trade_confidence > 0.7:
                what_failed.append(f"Overconfident ({pre_trade_confidence:.0%}) - calibration needed")
                pattern_tags.append("overconfidence")
            if pre_trade_confidence < 0.5:
                what_failed.append("Took trade despite low confidence - discipline issue")
                pattern_tags.append("low_conviction_trade")

        # Generate lesson learned
        if is_win:
            lesson = f"Continue pattern: {what_worked[0] if what_worked else 'Good execution'}"
            would_take_again = True
            improvement = "Maintain discipline, consider slightly larger position"
        else:
            lesson = f"Avoid pattern: {what_failed[0] if what_failed else 'Review entry criteria'}"
            would_take_again = False
            improvement = "Wait for better setup, reduce position size on uncertainty"

        # Add default entries if empty
        if not what_worked:
            what_worked.append("Entry timing" if is_win else "Limited loss")
        if not what_failed:
            what_failed.append("Nothing major" if is_win else "Entry timing")

        return TradeReflection(
            trade_id=trade_id,
            symbol=symbol,
            timestamp=datetime.now(timezone.utc).isoformat(),
            action=action,
            entry_price=entry_price,
            exit_price=exit_price,
            pnl=pnl,
            pnl_pct=pnl_pct,
            is_win=is_win,
            pre_trade_signals=pre_trade_signals,
            pre_trade_confidence=pre_trade_confidence,
            pre_trade_reasoning=pre_trade_reasoning,
            what_worked=what_worked,
            what_failed=what_failed,
            lesson_learned=lesson,
            would_take_again=would_take_again,
            improvement_action=improvement,
            pattern_tags=pattern_tags,
        )

    def store_reflection(self, reflection: TradeReflection) -> None:
        """
        Store a reflection in long-term memory.

        Also updates aggregate statistics and pattern analysis.
        """
        self.memory.reflections.append(reflection)
        self.memory.total_trades += 1

        # Update win rate
        wins = sum(1 for r in self.memory.reflections if r.is_win)
        self.memory.win_rate = wins / len(self.memory.reflections) if self.memory.reflections else 0

        # Update common mistakes (from losing trades)
        if not reflection.is_win:
            for mistake in reflection.what_failed:
                if mistake not in self.memory.common_mistakes:
                    self.memory.common_mistakes.append(mistake)
            # Keep only top 10 most recent mistakes
            self.memory.common_mistakes = self.memory.common_mistakes[-10:]

        # Update best patterns (from winning trades)
        if reflection.is_win:
            for pattern in reflection.pattern_tags:
                if pattern not in self.memory.best_patterns:
                    self.memory.best_patterns.append(pattern)
            self.memory.best_patterns = self.memory.best_patterns[-10:]

        self._save_memory()
        logger.info(f"Stored reflection for {reflection.symbol}: {'WIN' if reflection.is_win else 'LOSS'}")

    def get_relevant_reflections(
        self, symbol: str | None = None, limit: int = 5
    ) -> list[TradeReflection]:
        """
        Get relevant past reflections for context.

        Prioritizes:
        1. Same symbol reflections
        2. Recent reflections
        3. Both wins and losses (for balanced learning)

        Args:
            symbol: Optional filter by symbol
            limit: Maximum number to return

        Returns:
            List of relevant reflections
        """
        reflections = self.memory.reflections

        if symbol:
            # Prioritize same symbol
            same_symbol = [r for r in reflections if r.symbol == symbol]
            other_symbol = [r for r in reflections if r.symbol != symbol]

            # Mix: 60% same symbol, 40% other (for generalization)
            same_limit = int(limit * 0.6)
            other_limit = limit - same_limit

            result = same_symbol[-same_limit:] + other_symbol[-other_limit:]
        else:
            result = reflections[-limit:]

        return result

    def generate_reflection_context(self, symbol: str | None = None) -> str:
        """
        Generate reflection context for LLM prompt injection.

        This is the KEY METHOD that feeds past learnings into future decisions.

        Args:
            symbol: Optional symbol to prioritize

        Returns:
            Formatted string for prompt injection
        """
        if not self.memory.reflections:
            return ""

        relevant = self.get_relevant_reflections(symbol, limit=5)

        context_parts = [
            "",
            "=" * 60,
            "REFLEXION: LESSONS FROM PAST TRADES",
            "=" * 60,
            "",
            f"Trade History: {self.memory.total_trades} trades | Win Rate: {self.memory.win_rate:.1%}",
            "",
        ]

        # Add recent lessons
        context_parts.append("RECENT LESSONS LEARNED:")
        for r in relevant[-3:]:
            outcome = "WIN" if r.is_win else "LOSS"
            context_parts.append(
                f"- [{outcome}] {r.symbol}: {r.lesson_learned}"
            )

        # Add common mistakes to avoid
        if self.memory.common_mistakes:
            context_parts.extend([
                "",
                "MISTAKES TO AVOID (from recent losses):",
            ])
            for mistake in self.memory.common_mistakes[-3:]:
                context_parts.append(f"- {mistake}")

        # Add best patterns to look for
        if self.memory.best_patterns:
            context_parts.extend([
                "",
                "PATTERNS THAT WORK (from recent wins):",
            ])
            for pattern in self.memory.best_patterns[-3:]:
                context_parts.append(f"- {pattern.replace('_', ' ').title()}")

        context_parts.extend([
            "",
            "Apply these lessons to the current decision.",
            "=" * 60,
        ])

        return "\n".join(context_parts)


# Singleton instance
_reflexion_loop: ReflexionLoop | None = None


def get_reflexion_loop() -> ReflexionLoop:
    """Get the singleton reflexion loop instance."""
    global _reflexion_loop
    if _reflexion_loop is None:
        _reflexion_loop = ReflexionLoop()
    return _reflexion_loop


def reflect_and_store(
    trade_id: str,
    symbol: str,
    action: str,
    entry_price: float,
    exit_price: float | None,
    pnl: float,
    pre_trade_signals: dict[str, Any],
    pre_trade_confidence: float,
    pre_trade_reasoning: str,
) -> TradeReflection:
    """
    Convenience function to reflect on and store a trade.

    Call this after every trade closes.
    """
    loop = get_reflexion_loop()
    reflection = loop.reflect_on_trade(
        trade_id=trade_id,
        symbol=symbol,
        action=action,
        entry_price=entry_price,
        exit_price=exit_price,
        pnl=pnl,
        pre_trade_signals=pre_trade_signals,
        pre_trade_confidence=pre_trade_confidence,
        pre_trade_reasoning=pre_trade_reasoning,
    )
    loop.store_reflection(reflection)
    return reflection


def get_reflection_context(symbol: str | None = None) -> str:
    """
    Get reflection context for LLM prompt injection.

    Call this before making trading decisions.
    """
    return get_reflexion_loop().generate_reflection_context(symbol)
