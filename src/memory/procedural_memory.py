"""
Procedural Memory for Trading Skills.

Based on Mem^p and LEGOMem frameworks for agent procedural memory.
Learns, stores, retrieves, and reuses successful trading patterns as skills.

Key Concepts:
- Skills are learned from successful trade trajectories
- Each skill has: conditions, actions, outcomes, embeddings
- Skills are retrieved by similarity when conditions match
- Skills improve over time through reinforcement

Usage:
    from src.memory import get_skill_library, TradingSkill

    library = get_skill_library()

    # Learn from a successful trade
    skill = library.extract_skill_from_trade(trade_record)

    # Find relevant skills for current conditions
    skills = library.retrieve_skills(
        market_conditions={"rsi": 75, "trend": "up", "volume": "high"}
    )

    # Execute a skill
    action = skills[0].get_action(current_context)

References:
- Mem^p: arxiv.org/html/2508.06433v2
- LEGOMem: arxiv.org/html/2510.04851
- MarkTechPost Procedural Memory Guide (Dec 2025)
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SkillType(Enum):
    """Types of trading skills."""

    ENTRY = "entry"  # When to enter a position
    EXIT = "exit"  # When to exit a position
    SIZING = "sizing"  # Position sizing
    TIMING = "timing"  # Timing optimization
    RISK = "risk"  # Risk management
    COMPOSITE = "composite"  # Multi-step workflow


class MarketRegime(Enum):
    """Market regime conditions."""

    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    QUIET = "quiet"


@dataclass
class SkillConditions:
    """Conditions under which a skill is applicable."""

    # Technical conditions
    rsi_range: tuple[float, float] = (0, 100)
    macd_signal: Optional[str] = None  # "bullish", "bearish", "neutral"
    trend: Optional[str] = None  # "up", "down", "sideways"
    volume_condition: Optional[str] = None  # "high", "normal", "low"

    # Market regime
    regime: Optional[MarketRegime] = None

    # Time conditions
    time_of_day: Optional[str] = None  # "market_open", "midday", "market_close"
    day_of_week: Optional[str] = None

    # Asset conditions
    volatility_percentile: Optional[tuple[float, float]] = None

    # Custom conditions (flexible key-value)
    custom: dict[str, Any] = field(default_factory=dict)

    def matches(self, context: dict[str, Any]) -> tuple[bool, float]:
        """
        Check if conditions match the given context.

        Returns (matches, score) where score is 0-1 indicating match quality.
        """
        score = 0.0
        checks = 0

        # RSI check
        if "rsi" in context:
            checks += 1
            rsi = context["rsi"]
            if self.rsi_range[0] <= rsi <= self.rsi_range[1]:
                score += 1.0

        # Trend check
        if self.trend and "trend" in context:
            checks += 1
            if context["trend"] == self.trend:
                score += 1.0

        # Volume check
        if self.volume_condition and "volume" in context:
            checks += 1
            if context["volume"] == self.volume_condition:
                score += 1.0

        # Regime check
        if self.regime and "regime" in context:
            checks += 1
            if context["regime"] == self.regime.value:
                score += 1.0

        # MACD check
        if self.macd_signal and "macd_signal" in context:
            checks += 1
            if context["macd_signal"] == self.macd_signal:
                score += 1.0

        # Asset class check
        if self.asset_class and "asset_class" in context:
            checks += 1
            if context["asset_class"] == self.asset_class:
                score += 1.0

        # Custom conditions
        for key, expected in self.custom.items():
            if key in context:
                checks += 1
                if context[key] == expected:
                    score += 1.0

        # Calculate match score
        match_score = score / checks if checks > 0 else 0.5
        matches = match_score >= 0.5  # At least half conditions must match

        return matches, match_score

    def to_dict(self) -> dict[str, Any]:
        return {
            "rsi_range": list(self.rsi_range),
            "macd_signal": self.macd_signal,
            "trend": self.trend,
            "volume_condition": self.volume_condition,
            "regime": self.regime.value if self.regime else None,
            "time_of_day": self.time_of_day,
            "day_of_week": self.day_of_week,
            "asset_class": self.asset_class,
            "volatility_percentile": list(self.volatility_percentile)
            if self.volatility_percentile
            else None,
            "custom": self.custom,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillConditions:
        return cls(
            rsi_range=tuple(data.get("rsi_range", [0, 100])),
            macd_signal=data.get("macd_signal"),
            trend=data.get("trend"),
            volume_condition=data.get("volume_condition"),
            regime=MarketRegime(data["regime"]) if data.get("regime") else None,
            time_of_day=data.get("time_of_day"),
            day_of_week=data.get("day_of_week"),
            asset_class=data.get("asset_class"),
            volatility_percentile=tuple(data["volatility_percentile"])
            if data.get("volatility_percentile")
            else None,
            custom=data.get("custom", {}),
        )


@dataclass
class SkillAction:
    """Action to take when skill is triggered."""

    action_type: str  # "buy", "sell", "hold", "scale_in", "scale_out"
    parameters: dict[str, Any] = field(default_factory=dict)

    # Position sizing
    size_method: str = "fixed"  # "fixed", "volatility_adjusted", "kelly"
    size_value: float = 1.0  # Percentage or fixed amount

    # Entry/Exit parameters
    entry_type: str = "market"  # "market", "limit", "stop"
    limit_offset_pct: float = 0.0

    # Stop loss / Take profit
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    trailing_stop_pct: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type,
            "parameters": self.parameters,
            "size_method": self.size_method,
            "size_value": self.size_value,
            "entry_type": self.entry_type,
            "limit_offset_pct": self.limit_offset_pct,
            "stop_loss_pct": self.stop_loss_pct,
            "take_profit_pct": self.take_profit_pct,
            "trailing_stop_pct": self.trailing_stop_pct,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillAction:
        return cls(
            action_type=data["action_type"],
            parameters=data.get("parameters", {}),
            size_method=data.get("size_method", "fixed"),
            size_value=data.get("size_value", 1.0),
            entry_type=data.get("entry_type", "market"),
            limit_offset_pct=data.get("limit_offset_pct", 0.0),
            stop_loss_pct=data.get("stop_loss_pct"),
            take_profit_pct=data.get("take_profit_pct"),
            trailing_stop_pct=data.get("trailing_stop_pct"),
        )


@dataclass
class SkillOutcome:
    """Expected and historical outcomes of a skill."""

    # Historical performance
    uses: int = 0
    wins: int = 0
    losses: int = 0
    total_profit_pct: float = 0.0
    avg_profit_pct: float = 0.0
    max_drawdown_pct: float = 0.0

    # Expected values
    expected_win_rate: float = 0.5
    expected_profit_pct: float = 0.0
    expected_duration_minutes: float = 60.0

    # Confidence
    confidence: float = 0.5  # Increases with successful uses

    def update(self, profit_pct: float, duration_minutes: float):
        """Update outcome stats with a new result."""
        self.uses += 1

        if profit_pct > 0:
            self.wins += 1
        else:
            self.losses += 1

        self.total_profit_pct += profit_pct
        self.avg_profit_pct = self.total_profit_pct / self.uses

        # Update expected values (exponential moving average)
        alpha = 0.3
        self.expected_win_rate = (
            alpha * (1 if profit_pct > 0 else 0) + (1 - alpha) * self.expected_win_rate
        )
        self.expected_profit_pct = alpha * profit_pct + (1 - alpha) * self.expected_profit_pct
        self.expected_duration_minutes = (
            alpha * duration_minutes + (1 - alpha) * self.expected_duration_minutes
        )

        # Update confidence (increases with uses, weighted by success)
        win_rate = self.wins / self.uses if self.uses > 0 else 0.5
        self.confidence = min(0.95, 0.5 + (self.uses / 100) * win_rate)

        # Track max drawdown
        if profit_pct < self.max_drawdown_pct:
            self.max_drawdown_pct = profit_pct

    def to_dict(self) -> dict[str, Any]:
        return {
            "uses": self.uses,
            "wins": self.wins,
            "losses": self.losses,
            "total_profit_pct": self.total_profit_pct,
            "avg_profit_pct": self.avg_profit_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
            "expected_win_rate": self.expected_win_rate,
            "expected_profit_pct": self.expected_profit_pct,
            "expected_duration_minutes": self.expected_duration_minutes,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillOutcome:
        return cls(
            uses=data.get("uses", 0),
            wins=data.get("wins", 0),
            losses=data.get("losses", 0),
            total_profit_pct=data.get("total_profit_pct", 0.0),
            avg_profit_pct=data.get("avg_profit_pct", 0.0),
            max_drawdown_pct=data.get("max_drawdown_pct", 0.0),
            expected_win_rate=data.get("expected_win_rate", 0.5),
            expected_profit_pct=data.get("expected_profit_pct", 0.0),
            expected_duration_minutes=data.get("expected_duration_minutes", 60.0),
            confidence=data.get("confidence", 0.5),
        )


@dataclass
class TradingSkill:
    """
    A learned trading skill - reusable pattern from successful trades.

    Like a "neural module" that encodes:
    - WHEN to act (conditions)
    - WHAT to do (action)
    - EXPECTED results (outcome)
    """

    skill_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    description: str = ""
    skill_type: SkillType = SkillType.ENTRY

    # Core components
    conditions: SkillConditions = field(default_factory=SkillConditions)
    action: SkillAction = field(default_factory=SkillAction)
    outcome: SkillOutcome = field(default_factory=SkillOutcome)

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source_trades: list[str] = field(default_factory=list)  # Trade IDs this skill was learned from

    # Embedding for semantic retrieval
    embedding: Optional[list[float]] = None

    # Tags for filtering
    tags: list[str] = field(default_factory=list)

    # Active flag
    active: bool = True

    def get_embedding_text(self) -> str:
        """Generate text for embedding."""
        parts = [
            f"Skill: {self.name}",
            f"Type: {self.skill_type.value}",
            f"Description: {self.description}",
            f"Action: {self.action.action_type}",
        ]

        if self.conditions.trend:
            parts.append(f"Trend: {self.conditions.trend}")
        if self.conditions.regime:
            parts.append(f"Regime: {self.conditions.regime.value}")
        if self.conditions.macd_signal:
            parts.append(f"MACD: {self.conditions.macd_signal}")

        parts.append(f"Win rate: {self.outcome.expected_win_rate:.0%}")
        parts.append(f"Avg profit: {self.outcome.avg_profit_pct:+.1f}%")

        return " | ".join(parts)

    def matches_context(self, context: dict[str, Any]) -> tuple[bool, float]:
        """Check if this skill applies to the given context."""
        return self.conditions.matches(context)

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "skill_type": self.skill_type.value,
            "conditions": self.conditions.to_dict(),
            "action": self.action.to_dict(),
            "outcome": self.outcome.to_dict(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "source_trades": self.source_trades,
            "embedding": self.embedding,
            "tags": self.tags,
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TradingSkill:
        return cls(
            skill_id=data["skill_id"],
            name=data["name"],
            description=data.get("description", ""),
            skill_type=SkillType(data["skill_type"]),
            conditions=SkillConditions.from_dict(data["conditions"]),
            action=SkillAction.from_dict(data["action"]),
            outcome=SkillOutcome.from_dict(data["outcome"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            source_trades=data.get("source_trades", []),
            embedding=data.get("embedding"),
            tags=data.get("tags", []),
            active=data.get("active", True),
        )


class SkillLibrary:
    """
    Library of trading skills with semantic retrieval.

    Implements the "skill bank" concept from LEGOMem:
    - Store skills indexed by conditions and embeddings
    - Retrieve by similarity when context matches
    - Learn new skills from successful trades
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path("data/skills")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.skills_file = self.storage_path / "skill_library.json"
        self.skills: dict[str, TradingSkill] = {}

        self._load_skills()
        self._init_embedder()

        logger.info(f"SkillLibrary initialized with {len(self.skills)} skills")

    def _init_embedder(self):
        """Initialize embedding model for semantic retrieval."""
        self._embedder = None
        try:
            from sentence_transformers import SentenceTransformer

            self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Sentence transformer loaded for skill embeddings")
        except ImportError:
            logger.warning("sentence-transformers not installed, using keyword matching only")

    def _load_skills(self):
        """Load skills from storage."""
        if self.skills_file.exists():
            try:
                with open(self.skills_file) as f:
                    data = json.load(f)
                    for skill_data in data.get("skills", []):
                        skill = TradingSkill.from_dict(skill_data)
                        self.skills[skill.skill_id] = skill
            except Exception as e:
                logger.warning(f"Failed to load skills: {e}")

    def _save_skills(self):
        """Save skills to storage."""
        data = {
            "version": "1.0",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "skills": [skill.to_dict() for skill in self.skills.values()],
        }

        with open(self.skills_file, "w") as f:
            json.dump(data, f, indent=2)

    def _compute_embedding(self, text: str) -> Optional[list[float]]:
        """Compute embedding for text."""
        if self._embedder is None:
            return None

        try:
            embedding = self._embedder.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            logger.warning(f"Failed to compute embedding: {e}")
            return None

    def add_skill(self, skill: TradingSkill) -> str:
        """Add a skill to the library."""
        # Compute embedding
        if skill.embedding is None:
            skill.embedding = self._compute_embedding(skill.get_embedding_text())

        self.skills[skill.skill_id] = skill
        self._save_skills()

        logger.info(f"Added skill: {skill.name} ({skill.skill_id})")
        return skill.skill_id

    def get_skill(self, skill_id: str) -> Optional[TradingSkill]:
        """Get a skill by ID."""
        return self.skills.get(skill_id)

    def retrieve_skills(
        self,
        context: dict[str, Any],
        skill_type: Optional[SkillType] = None,
        min_confidence: float = 0.3,
        top_k: int = 5,
    ) -> list[tuple[TradingSkill, float]]:
        """
        Retrieve relevant skills for the given context.

        Returns list of (skill, relevance_score) tuples.
        """
        candidates = []

        for skill in self.skills.values():
            if not skill.active:
                continue

            if skill_type and skill.skill_type != skill_type:
                continue

            if skill.outcome.confidence < min_confidence:
                continue

            matches, match_score = skill.matches_context(context)
            if matches:
                # Combine match score with outcome confidence
                relevance = match_score * 0.6 + skill.outcome.confidence * 0.4
                candidates.append((skill, relevance))

        # Sort by relevance
        candidates.sort(key=lambda x: x[1], reverse=True)

        return candidates[:top_k]

    def retrieve_by_similarity(
        self,
        query: str,
        skill_type: Optional[SkillType] = None,
        top_k: int = 5,
    ) -> list[tuple[TradingSkill, float]]:
        """Retrieve skills by semantic similarity to query."""
        if self._embedder is None:
            logger.warning("No embedder available for similarity search")
            return []

        query_embedding = self._compute_embedding(query)
        if query_embedding is None:
            return []

        candidates = []
        for skill in self.skills.values():
            if not skill.active:
                continue

            if skill_type and skill.skill_type != skill_type:
                continue

            if skill.embedding is None:
                continue

            # Cosine similarity
            similarity = self._cosine_similarity(query_embedding, skill.embedding)
            candidates.append((skill, similarity))

        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:top_k]

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        import math

        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    def extract_skill_from_trade(
        self,
        trade_record: dict[str, Any],
        name: Optional[str] = None,
    ) -> Optional[TradingSkill]:
        """
        Extract a skill from a successful trade record.

        This is the core "learning" function - converts experience to skill.
        """
        # Only learn from profitable trades
        profit_pct = trade_record.get("profit_pct", 0)
        if profit_pct <= 0:
            logger.debug("Skipping non-profitable trade for skill extraction")
            return None

        # Extract conditions from trade context
        conditions = SkillConditions(
            rsi_range=(
                trade_record.get("rsi", 50) - 10,
                trade_record.get("rsi", 50) + 10,
            ),
            trend=trade_record.get("trend"),
            macd_signal=trade_record.get("macd_signal"),
            volume_condition=trade_record.get("volume"),
            regime=MarketRegime(trade_record["regime"]) if trade_record.get("regime") else None,
            asset_class=trade_record.get("asset_class"),
        )

        # Extract action
        action = SkillAction(
            action_type=trade_record.get("action", "buy"),
            size_method=trade_record.get("size_method", "fixed"),
            size_value=trade_record.get("size_value", 1.0),
            stop_loss_pct=trade_record.get("stop_loss_pct"),
            take_profit_pct=trade_record.get("take_profit_pct"),
        )

        # Initialize outcome
        outcome = SkillOutcome(
            uses=1,
            wins=1,
            total_profit_pct=profit_pct,
            avg_profit_pct=profit_pct,
            expected_win_rate=0.6,  # Start optimistic for new skills
            expected_profit_pct=profit_pct,
            confidence=0.4,  # Low confidence initially
        )

        # Generate name
        if name is None:
            name = self._generate_skill_name(conditions, action)

        # Create skill
        skill = TradingSkill(
            name=name,
            description=f"Learned from trade on {trade_record.get('symbol', 'unknown')}",
            skill_type=SkillType.ENTRY if action.action_type == "buy" else SkillType.EXIT,
            conditions=conditions,
            action=action,
            outcome=outcome,
            source_trades=[trade_record.get("trade_id", str(uuid.uuid4())[:8])],
            tags=[
                trade_record.get("symbol", "unknown"),
                conditions.trend or "unknown_trend",
            ],
        )

        # Check for similar existing skill
        similar = self._find_similar_skill(skill)
        if similar:
            # Merge into existing skill
            self._merge_skill(similar, skill, trade_record)
            return similar

        # Add as new skill
        self.add_skill(skill)
        return skill

    def _generate_skill_name(self, conditions: SkillConditions, action: SkillAction) -> str:
        """Generate a descriptive name for a skill."""
        parts = []

        if conditions.trend:
            parts.append(conditions.trend.capitalize())

        if conditions.regime:
            parts.append(conditions.regime.value.replace("_", " ").title())

        parts.append(action.action_type.upper())

        if conditions.rsi_range[0] > 60:
            parts.append("Overbought")
        elif conditions.rsi_range[1] < 40:
            parts.append("Oversold")

        return " ".join(parts) if parts else "Generic Trade"

    def _find_similar_skill(self, skill: TradingSkill) -> Optional[TradingSkill]:
        """Find an existing skill similar to the given one."""
        for existing in self.skills.values():
            if existing.skill_type != skill.skill_type:
                continue

            # Check conditions similarity
            if (
                existing.conditions.trend == skill.conditions.trend
                and existing.conditions.regime == skill.conditions.regime
                and existing.action.action_type == skill.action.action_type
            ):
                # RSI range overlap
                rsi_overlap = max(
                    existing.conditions.rsi_range[0], skill.conditions.rsi_range[0]
                ) <= min(existing.conditions.rsi_range[1], skill.conditions.rsi_range[1])
                if rsi_overlap:
                    return existing

        return None

    def _merge_skill(
        self,
        existing: TradingSkill,
        new: TradingSkill,
        trade_record: dict[str, Any],
    ):
        """Merge a new skill observation into an existing skill."""
        # Update outcome stats
        profit_pct = trade_record.get("profit_pct", 0)
        duration = trade_record.get("duration_minutes", 60)
        existing.outcome.update(profit_pct, duration)

        # Add source trade
        existing.source_trades.append(trade_record.get("trade_id", ""))

        # Update timestamp
        existing.updated_at = datetime.now(timezone.utc)

        # Expand RSI range if needed
        existing.conditions.rsi_range = (
            min(existing.conditions.rsi_range[0], new.conditions.rsi_range[0]),
            max(existing.conditions.rsi_range[1], new.conditions.rsi_range[1]),
        )

        # Recompute embedding
        existing.embedding = self._compute_embedding(existing.get_embedding_text())

        self._save_skills()

        logger.info(
            f"Merged trade into skill {existing.name}: "
            f"uses={existing.outcome.uses}, win_rate={existing.outcome.expected_win_rate:.1%}"
        )

    def update_skill_outcome(self, skill_id: str, profit_pct: float, duration_minutes: float):
        """Update a skill's outcome after use."""
        skill = self.skills.get(skill_id)
        if skill:
            skill.outcome.update(profit_pct, duration_minutes)
            skill.updated_at = datetime.now(timezone.utc)
            self._save_skills()

    def get_best_skills(
        self,
        skill_type: Optional[SkillType] = None,
        min_uses: int = 3,
        top_k: int = 10,
    ) -> list[TradingSkill]:
        """Get the best performing skills."""
        candidates = []

        for skill in self.skills.values():
            if not skill.active:
                continue

            if skill_type and skill.skill_type != skill_type:
                continue

            if skill.outcome.uses < min_uses:
                continue

            # Score = win_rate * avg_profit * confidence
            score = (
                skill.outcome.expected_win_rate
                * max(0, skill.outcome.avg_profit_pct + 1)
                * skill.outcome.confidence
            )
            candidates.append((skill, score))

        candidates.sort(key=lambda x: x[1], reverse=True)
        return [skill for skill, _ in candidates[:top_k]]

    def deactivate_skill(self, skill_id: str, reason: str = ""):
        """Deactivate a skill (e.g., if it's no longer working)."""
        skill = self.skills.get(skill_id)
        if skill:
            skill.active = False
            skill.tags.append(f"deactivated:{reason}")
            self._save_skills()
            logger.info(f"Deactivated skill {skill_id}: {reason}")

    def get_skill_report(self) -> str:
        """Generate a report of all skills."""
        lines = [
            "=" * 60,
            "PROCEDURAL MEMORY - SKILL LIBRARY REPORT",
            f"Total Skills: {len(self.skills)}",
            f"Active Skills: {sum(1 for s in self.skills.values() if s.active)}",
            "=" * 60,
            "",
        ]

        # Group by type
        by_type: dict[SkillType, list[TradingSkill]] = {}
        for skill in self.skills.values():
            if skill.skill_type not in by_type:
                by_type[skill.skill_type] = []
            by_type[skill.skill_type].append(skill)

        for skill_type, skills in by_type.items():
            lines.append(f"\n{skill_type.value.upper()} SKILLS ({len(skills)})")
            lines.append("-" * 40)

            for skill in sorted(skills, key=lambda s: s.outcome.confidence, reverse=True):
                status = "ACTIVE" if skill.active else "INACTIVE"
                lines.append(f"  [{status}] {skill.name}")
                lines.append(
                    f"    Uses: {skill.outcome.uses} | "
                    f"Win Rate: {skill.outcome.expected_win_rate:.0%} | "
                    f"Avg Profit: {skill.outcome.avg_profit_pct:+.1f}% | "
                    f"Confidence: {skill.outcome.confidence:.0%}"
                )

        lines.append("\n" + "=" * 60)
        return "\n".join(lines)


class ProceduralMemory:
    """
    High-level interface for procedural memory in trading.

    Combines:
    - Skill learning from successful trades
    - Skill retrieval for decision making
    - Skill execution with outcome tracking
    """

    def __init__(self, library: Optional[SkillLibrary] = None):
        self.library = library or SkillLibrary()
        self._active_skills: dict[str, str] = {}  # trade_id -> skill_id

    def learn_from_trade(self, trade_record: dict[str, Any]) -> Optional[TradingSkill]:
        """Learn a skill from a completed trade."""
        return self.library.extract_skill_from_trade(trade_record)

    def suggest_action(
        self,
        context: dict[str, Any],
        skill_type: Optional[SkillType] = None,
    ) -> Optional[tuple[TradingSkill, SkillAction, float]]:
        """
        Suggest an action based on matching skills.

        Returns (skill, action, confidence) or None if no matching skill.
        """
        skills = self.library.retrieve_skills(context, skill_type=skill_type)

        if not skills:
            return None

        best_skill, relevance = skills[0]

        # Combine relevance with skill confidence
        confidence = relevance * best_skill.outcome.confidence

        return (best_skill, best_skill.action, confidence)

    def record_skill_use(
        self,
        skill_id: str,
        trade_id: str,
    ):
        """Record that a skill was used for a trade."""
        self._active_skills[trade_id] = skill_id

    def record_trade_outcome(
        self,
        trade_id: str,
        profit_pct: float,
        duration_minutes: float,
    ):
        """Record the outcome of a trade that used a skill."""
        skill_id = self._active_skills.pop(trade_id, None)
        if skill_id:
            self.library.update_skill_outcome(skill_id, profit_pct, duration_minutes)

    def get_report(self) -> str:
        """Get skill library report."""
        return self.library.get_skill_report()


# Global singleton
_library: Optional[SkillLibrary] = None


def get_skill_library(**kwargs) -> SkillLibrary:
    """Get the global skill library instance."""
    global _library
    if _library is None:
        _library = SkillLibrary(**kwargs)
    return _library
