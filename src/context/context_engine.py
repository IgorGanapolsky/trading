"""
Context Engineering Module for Trading System

Implements the 4 core strategies from LangChain/Anthropic research:
- Write: Persist analysis to scratchpads for cross-agent sharing
- Select: Semantic retrieval of only relevant context
- Compress: Summarize patterns to reduce token usage
- Isolate: Maintain separate contexts per agent

Reference: https://www.blog.langchain.com/context-engineering-for-agents/

Usage:
    from src.context.context_engine import ContextEngine

    engine = ContextEngine()

    # Write: Save analysis
    engine.write("fed_risk", {"speaker": "Bostic", "risk_delta": 0.3})

    # Select: Get relevant lessons
    lessons = engine.select("iron condor Fed volatility", top_k=3)

    # Compress: Get pattern summary
    patterns = engine.compress_lessons(lessons)

    # Isolate: Create agent-specific context
    agent_ctx = engine.isolate("technical_agent", max_tokens=2000)
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Project paths
PROJECT_DIR = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_DIR / "data"
SCRATCHPAD_DIR = DATA_DIR / "context" / "scratchpads"
PATTERNS_FILE = DATA_DIR / "context" / "compressed_patterns.json"

# Ensure directories exist
SCRATCHPAD_DIR.mkdir(parents=True, exist_ok=True)
PATTERNS_FILE.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class ContextEntry:
    """A single context entry with metadata."""

    key: str
    value: Any
    timestamp: datetime
    source: str  # Which agent/component wrote this
    ttl_hours: float = 4.0  # Default 4 hour TTL
    importance: float = 0.5  # 0-1, higher = more important

    @property
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        expiry = self.timestamp + timedelta(hours=self.ttl_hours)
        return datetime.now() > expiry

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "ttl_hours": self.ttl_hours,
            "importance": self.importance,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ContextEntry":
        return cls(
            key=data["key"],
            value=data["value"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            source=data["source"],
            ttl_hours=data.get("ttl_hours", 4.0),
            importance=data.get("importance", 0.5),
        )


@dataclass
class CompressedPattern:
    """A compressed pattern extracted from lessons."""

    pattern_id: str
    description: str
    trigger: str  # When this pattern applies
    action: str  # What to do
    confidence: float  # How reliable (based on supporting evidence)
    source_lessons: list[str]  # IDs of lessons that support this pattern
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "pattern_id": self.pattern_id,
            "description": self.description,
            "trigger": self.trigger,
            "action": self.action,
            "confidence": self.confidence,
            "source_lessons": self.source_lessons,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CompressedPattern":
        return cls(
            pattern_id=data["pattern_id"],
            description=data["description"],
            trigger=data["trigger"],
            action=data["action"],
            confidence=data["confidence"],
            source_lessons=data["source_lessons"],
            created_at=datetime.fromisoformat(data["created_at"]),
        )


class Scratchpad:
    """
    Write Strategy: Persistent scratchpad for cross-agent context sharing.

    Entries auto-expire after TTL to prevent context pollution.
    """

    def __init__(self, session_id: str | None = None):
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.file_path = SCRATCHPAD_DIR / f"session_{self.session_id}.json"
        self._entries: dict[str, ContextEntry] = {}
        self._load()

    def _load(self) -> None:
        """Load existing scratchpad from disk."""
        if self.file_path.exists():
            try:
                data = json.loads(self.file_path.read_text())
                for key, entry_data in data.get("entries", {}).items():
                    entry = ContextEntry.from_dict(entry_data)
                    if not entry.is_expired:
                        self._entries[key] = entry
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to load scratchpad: {e}")

    def _save(self) -> None:
        """Persist scratchpad to disk."""
        data = {
            "session_id": self.session_id,
            "updated_at": datetime.now().isoformat(),
            "entries": {k: v.to_dict() for k, v in self._entries.items()},
        }
        self.file_path.write_text(json.dumps(data, indent=2))

    def write(
        self,
        key: str,
        value: Any,
        source: str = "unknown",
        ttl_hours: float = 4.0,
        importance: float = 0.5,
    ) -> None:
        """Write a context entry to the scratchpad."""
        self._entries[key] = ContextEntry(
            key=key,
            value=value,
            timestamp=datetime.now(),
            source=source,
            ttl_hours=ttl_hours,
            importance=importance,
        )
        self._save()
        logger.debug(f"Scratchpad write: {key} from {source}")

    def read(self, key: str) -> Any | None:
        """Read a context entry, returns None if expired or missing."""
        entry = self._entries.get(key)
        if entry and not entry.is_expired:
            return entry.value
        return None

    def read_all(self, min_importance: float = 0.0) -> dict[str, Any]:
        """Read all non-expired entries above importance threshold."""
        return {
            k: v.value
            for k, v in self._entries.items()
            if not v.is_expired and v.importance >= min_importance
        }

    def clear_expired(self) -> int:
        """Remove expired entries, return count removed."""
        expired = [k for k, v in self._entries.items() if v.is_expired]
        for k in expired:
            del self._entries[k]
        if expired:
            self._save()
        return len(expired)


class PatternCompressor:
    """
    Compress Strategy: Extract and summarize patterns from lessons.

    Reduces 182 lessons to ~20 actionable patterns.
    """

    # Pre-defined trading patterns (seeded from analysis)
    SEED_PATTERNS = [
        CompressedPattern(
            pattern_id="PAT001",
            description="Fed speakers increase SPY volatility",
            trigger="Fed speaker scheduled (FOMC, Powell, regional presidents)",
            action="Avoid opening new iron condors, or use wider strikes (+5 delta)",
            confidence=0.85,
            source_lessons=["LL-220", "LL-268"],
        ),
        CompressedPattern(
            pattern_id="PAT002",
            description="Earnings week correlation risk",
            trigger="Major S&P 500 company reporting (AAPL, MSFT, NVDA, etc.)",
            action="Check if company is >2% of SPY weight, avoid if reporting",
            confidence=0.80,
            source_lessons=["LL-230"],
        ),
        CompressedPattern(
            pattern_id="PAT003",
            description="15-delta iron condors have 86% win rate",
            trigger="Opening new iron condor position",
            action="Use 15-20 delta for short strikes, not tighter",
            confidence=0.90,
            source_lessons=["LL-220"],
        ),
        CompressedPattern(
            pattern_id="PAT004",
            description="Close at 7 DTE to avoid gamma risk",
            trigger="Iron condor approaching expiration",
            action="Close position at 7 DTE regardless of profit level",
            confidence=0.85,
            source_lessons=["LL-268"],
        ),
        CompressedPattern(
            pattern_id="PAT005",
            description="Stop loss at 200% of credit",
            trigger="Position moving against you",
            action="Close if loss reaches 2x the premium received - NO EXCEPTIONS",
            confidence=0.95,
            source_lessons=["LL-268", "CLAUDE.md"],
        ),
    ]

    def __init__(self):
        self.patterns: list[CompressedPattern] = []
        self._load()

    def _load(self) -> None:
        """Load patterns from disk or seed with defaults."""
        if PATTERNS_FILE.exists():
            try:
                data = json.loads(PATTERNS_FILE.read_text())
                self.patterns = [
                    CompressedPattern.from_dict(p) for p in data.get("patterns", [])
                ]
            except (json.JSONDecodeError, KeyError):
                self.patterns = self.SEED_PATTERNS.copy()
        else:
            self.patterns = self.SEED_PATTERNS.copy()
            self._save()

    def _save(self) -> None:
        """Persist patterns to disk."""
        data = {
            "updated_at": datetime.now().isoformat(),
            "count": len(self.patterns),
            "patterns": [p.to_dict() for p in self.patterns],
        }
        PATTERNS_FILE.write_text(json.dumps(data, indent=2))

    def get_relevant_patterns(self, context: str) -> list[CompressedPattern]:
        """Get patterns relevant to the current context."""
        context_lower = context.lower()
        relevant = []

        for pattern in self.patterns:
            # Simple keyword matching (could be upgraded to embeddings)
            trigger_words = pattern.trigger.lower().split()
            if any(word in context_lower for word in trigger_words if len(word) > 3):
                relevant.append(pattern)

        return sorted(relevant, key=lambda p: p.confidence, reverse=True)

    def add_pattern(
        self,
        description: str,
        trigger: str,
        action: str,
        confidence: float,
        source_lessons: list[str],
    ) -> CompressedPattern:
        """Add a new compressed pattern."""
        pattern_id = f"PAT{len(self.patterns) + 1:03d}"
        pattern = CompressedPattern(
            pattern_id=pattern_id,
            description=description,
            trigger=trigger,
            action=action,
            confidence=confidence,
            source_lessons=source_lessons,
        )
        self.patterns.append(pattern)
        self._save()
        return pattern

    def to_context_string(self, patterns: list[CompressedPattern] | None = None) -> str:
        """Convert patterns to a compact context string."""
        patterns = patterns or self.patterns
        lines = ["## Trading Patterns (Compressed from 182 lessons)"]
        for p in patterns[:10]:  # Limit to top 10
            lines.append(f"- **{p.description}** (conf: {p.confidence:.0%})")
            lines.append(f"  - When: {p.trigger}")
            lines.append(f"  - Do: {p.action}")
        return "\n".join(lines)


class ContextSelector:
    """
    Select Strategy: Semantic retrieval of only relevant context.

    Integrates with existing LessonsLearnedRAG but filters aggressively.
    """

    def __init__(self):
        self._rag = None

    def _get_rag(self):
        """Lazy load RAG to avoid import cycles."""
        if self._rag is None:
            try:
                from src.rag.lessons_learned import LessonsLearnedRAG

                self._rag = LessonsLearnedRAG()
            except ImportError:
                logger.warning("LessonsLearnedRAG not available")
        return self._rag

    def select(self, query: str, top_k: int = 3, min_score: float = 0.5) -> list[dict]:
        """
        Select only the most relevant lessons for the current context.

        Unlike full RAG retrieval, this aggressively filters to minimize
        context window usage.
        """
        rag = self._get_rag()
        if not rag:
            return []

        try:
            results = rag.search(query, top_k=top_k * 2)  # Over-fetch then filter

            # Filter by score and deduplicate
            filtered = []
            seen_content = set()

            for lesson, score in results:
                if score < min_score:
                    continue

                # Hash content to detect near-duplicates (not for security)
                content_hash = hashlib.md5(  # noqa: S324
                    lesson.get("content", "")[:100].encode(),
                    usedforsecurity=False,
                ).hexdigest()[:8]

                if content_hash in seen_content:
                    continue
                seen_content.add(content_hash)

                filtered.append(
                    {
                        "id": lesson.get("id", "unknown"),
                        "title": lesson.get("title", ""),
                        "content": lesson.get("content", "")[:500],  # Truncate
                        "score": score,
                    }
                )

                if len(filtered) >= top_k:
                    break

            return filtered
        except Exception as e:
            logger.error(f"Context selection failed: {e}")
            return []


class AgentContext:
    """
    Isolate Strategy: Maintain separate contexts per agent.

    Each agent gets a focused context window without interference.
    """

    def __init__(self, agent_name: str, max_tokens: int = 2000):
        self.agent_name = agent_name
        self.max_tokens = max_tokens
        self._context_items: list[tuple[str, int]] = []  # (content, priority)

    def add(self, content: str, priority: int = 5) -> None:
        """Add content to agent's isolated context."""
        self._context_items.append((content, priority))

    def build(self) -> str:
        """Build the final context string within token budget."""
        # Sort by priority (higher = more important)
        sorted_items = sorted(self._context_items, key=lambda x: x[1], reverse=True)

        result = []
        current_tokens = 0

        for content, _ in sorted_items:
            # Rough token estimate: ~4 chars per token
            content_tokens = len(content) // 4

            if current_tokens + content_tokens > self.max_tokens:
                # Truncate last item to fit
                remaining = self.max_tokens - current_tokens
                if remaining > 100:  # Only add if meaningful
                    result.append(content[: remaining * 4] + "...")
                break

            result.append(content)
            current_tokens += content_tokens

        return "\n\n".join(result)


class ContextEngine:
    """
    Unified Context Engineering interface.

    Combines all 4 strategies (Write, Select, Compress, Isolate) into
    a single, easy-to-use API for the trading system.
    """

    def __init__(self, session_id: str | None = None):
        self.scratchpad = Scratchpad(session_id)
        self.compressor = PatternCompressor()
        self.selector = ContextSelector()
        self._agent_contexts: dict[str, AgentContext] = {}

    # =========================================================================
    # Write Strategy
    # =========================================================================

    def write(
        self,
        key: str,
        value: Any,
        source: str = "system",
        ttl_hours: float = 4.0,
        importance: float = 0.5,
    ) -> None:
        """Write analysis to scratchpad for cross-agent sharing."""
        self.scratchpad.write(key, value, source, ttl_hours, importance)

    def read(self, key: str) -> Any | None:
        """Read from scratchpad."""
        return self.scratchpad.read(key)

    def read_all(self, min_importance: float = 0.0) -> dict[str, Any]:
        """Read all high-importance scratchpad entries."""
        return self.scratchpad.read_all(min_importance)

    # =========================================================================
    # Select Strategy
    # =========================================================================

    def select(self, query: str, top_k: int = 3) -> list[dict]:
        """Select only relevant lessons for current context."""
        return self.selector.select(query, top_k)

    # =========================================================================
    # Compress Strategy
    # =========================================================================

    def get_patterns(self, context: str | None = None) -> list[CompressedPattern]:
        """Get compressed patterns, optionally filtered by context."""
        if context:
            return self.compressor.get_relevant_patterns(context)
        return self.compressor.patterns

    def patterns_as_context(self, context: str | None = None) -> str:
        """Get patterns formatted for LLM context."""
        patterns = self.get_patterns(context)
        return self.compressor.to_context_string(patterns)

    # =========================================================================
    # Isolate Strategy
    # =========================================================================

    def isolate(self, agent_name: str, max_tokens: int = 2000) -> AgentContext:
        """Create or get an isolated context for an agent."""
        if agent_name not in self._agent_contexts:
            self._agent_contexts[agent_name] = AgentContext(agent_name, max_tokens)
        return self._agent_contexts[agent_name]

    def clear_agent_context(self, agent_name: str) -> None:
        """Clear an agent's isolated context."""
        if agent_name in self._agent_contexts:
            del self._agent_contexts[agent_name]

    # =========================================================================
    # Convenience Methods
    # =========================================================================

    def build_trading_context(
        self,
        agent_name: str,
        query: str | None = None,
        include_patterns: bool = True,
        include_scratchpad: bool = True,
        max_tokens: int = 2000,
    ) -> str:
        """
        Build a complete, optimized context for a trading agent.

        This is the main entry point for context engineering.
        """
        ctx = self.isolate(agent_name, max_tokens)

        # Add compressed patterns (high priority)
        if include_patterns:
            patterns_ctx = self.patterns_as_context(query)
            ctx.add(patterns_ctx, priority=10)

        # Add relevant lessons (medium priority)
        if query:
            lessons = self.select(query, top_k=3)
            if lessons:
                lessons_ctx = "## Relevant Lessons\n"
                for lesson in lessons:
                    lessons_ctx += (
                        f"- **{lesson['id']}**: {lesson['content'][:200]}...\n"
                    )
                ctx.add(lessons_ctx, priority=7)

        # Add scratchpad (recent analysis, medium-high priority)
        if include_scratchpad:
            scratchpad_data = self.read_all(min_importance=0.3)
            if scratchpad_data:
                scratchpad_ctx = "## Session Analysis\n"
                for k, v in scratchpad_data.items():
                    if isinstance(v, dict):
                        scratchpad_ctx += f"- {k}: {json.dumps(v)[:100]}\n"
                    else:
                        scratchpad_ctx += f"- {k}: {v}\n"
                ctx.add(scratchpad_ctx, priority=8)

        return ctx.build()


# Singleton instance for easy access
_engine: ContextEngine | None = None


def get_context_engine(session_id: str | None = None) -> ContextEngine:
    """Get or create the singleton context engine."""
    global _engine
    if _engine is None:
        _engine = ContextEngine(session_id)
    return _engine
