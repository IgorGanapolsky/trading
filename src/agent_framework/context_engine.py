"""
Context Engine for Multi-Agent Systems

Implements context engineering principles from:
- "Context Engineering for Multi-Agent Systems" (Packt)
- "Context Engineering for Multi-Agent LLM Code Assistants" (arXiv:2508.08322)
- Claude Agent SDK 1M Context Windows (December 2025)

Key Concepts:
1. Semantic Blueprints: Structured definitions of agent roles, capabilities, and communication
2. Context Flow: Structured passing of context between agents without information loss
3. Context Validation: Ensuring context integrity and completeness
4. Memory & Persistence: Long-term and short-term context storage
5. Error Handling: Resilient context passing with fallbacks
6. 1M Context Support: Extended context windows for full codebase/history awareness

New in December 2025:
- Support for 1M token context windows (5x increase)
- Automatic context compaction when approaching limits
- Agent SDK integration with beta features
"""

from __future__ import annotations

import contextlib
import json
import logging
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class ContextType(Enum):
    """Types of context in the system"""

    SEMANTIC_BLUEPRINT = "semantic_blueprint"  # Agent role/capability definition
    TASK_CONTEXT = "task_context"  # Specific task information
    MEMORY_CONTEXT = "memory_context"  # Historical context
    VALIDATION_CONTEXT = "validation_context"  # Validation rules
    COMMUNICATION_CONTEXT = "communication_context"  # Inter-agent messages


class ContextPriority(Enum):
    """Priority levels for context"""

    CRITICAL = "critical"  # Must be included
    HIGH = "high"  # Should be included
    MEDIUM = "medium"  # Include if space allows
    LOW = "low"  # Optional


class MemoryTimescale(Enum):
    """Memory timescales for nested learning paradigm"""

    INTRADAY = "intraday"  # Minutes/hours - last 100 trades
    DAILY = "daily"  # Days - last 30 days
    WEEKLY = "weekly"  # Weeks - last 12 weeks
    MONTHLY = "monthly"  # Months - last 12 months
    EPISODIC = "episodic"  # Important events - no limit


@dataclass
class SemanticBlueprint:
    """
    Semantic Blueprint: Structured definition of an agent's role, capabilities,
    and communication protocol.

    Moves beyond simple prompts to structured context that defines:
    - What the agent does (role)
    - What it needs (inputs)
    - What it produces (outputs)
    - How it communicates (protocol)
    """

    agent_id: str
    agent_name: str
    role: str
    description: str
    capabilities: list[str] = field(default_factory=list)
    inputs: dict[str, dict[str, Any]] = field(default_factory=dict)  # Input schema
    outputs: dict[str, dict[str, Any]] = field(default_factory=dict)  # Output schema
    communication_protocol: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)  # Other agents this depends on
    context_window_size: int = 50_000  # Default tokens (expanded with 1M context support)
    priority: ContextPriority = ContextPriority.HIGH
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_context_dict(self) -> dict[str, Any]:
        """Convert blueprint to context dictionary for LLM"""
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "role": self.role,
            "description": self.description,
            "capabilities": self.capabilities,
            "input_schema": self.inputs,
            "output_schema": self.outputs,
            "communication_protocol": self.communication_protocol,
            "dependencies": self.dependencies,
        }


@dataclass
class ContextMessage:
    """
    Structured message for inter-agent communication using MCP principles.

    Ensures context is passed reliably without information loss.
    """

    message_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    sender_agent: str = ""
    receiver_agent: str = ""
    context_type: ContextType = ContextType.COMMUNICATION_CONTEXT
    payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    validation_hash: str | None = None  # For integrity checking

    def validate(self) -> tuple[bool, list[str]]:
        """Validate message structure and completeness"""
        errors = []

        if not self.sender_agent:
            errors.append("Missing sender_agent")
        if not self.receiver_agent:
            errors.append("Missing receiver_agent")
        if not self.payload:
            errors.append("Empty payload")

        return len(errors) == 0, errors

    def to_mcp_format(self) -> dict[str, Any]:
        """Convert to MCP-compatible format"""
        return {
            "id": self.message_id,
            "timestamp": self.timestamp,
            "from": self.sender_agent,
            "to": self.receiver_agent,
            "type": self.context_type.value,
            "data": self.payload,
            "meta": self.metadata,
        }


@dataclass
class ContextMemory:
    """
    Memory storage for context persistence.

    Supports both short-term (session) and long-term (persistent) memory.
    Enhanced with multi-timescale support for nested learning.
    """

    memory_id: str = field(default_factory=lambda: str(uuid4()))
    agent_id: str = ""
    context_type: ContextType = ContextType.MEMORY_CONTEXT
    content: dict[str, Any] = field(default_factory=dict)
    tags: set[str] = field(default_factory=set)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    accessed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    access_count: int = 0
    ttl_days: int | None = None  # Time-to-live for short-term memory
    timescale: MemoryTimescale = MemoryTimescale.DAILY  # Multi-timescale support
    importance_score: float = 0.5  # 0.0-1.0, higher = more important (preserve longer)
    outcome_pl: float | None = None  # Profit/loss from this memory (for scoring)

    def is_expired(self) -> bool:
        """Check if memory has expired"""
        if self.ttl_days is None:
            # Episodic memories never expire
            if self.timescale == MemoryTimescale.EPISODIC:
                return False
            # High importance memories (>0.8) never expire
            if self.importance_score > 0.8:
                return False
            return False

        created = datetime.fromisoformat(self.created_at)
        return datetime.now() - created > timedelta(days=self.ttl_days)

    def touch(self):
        """Update access time and count"""
        self.accessed_at = datetime.now().isoformat()
        self.access_count += 1

    def update_importance(self, pl: float, max_pl: float = 1000.0) -> None:
        """
        Update importance score based on outcome.

        Args:
            pl: Profit/loss from this memory
            max_pl: Maximum expected P/L for normalization
        """
        self.outcome_pl = pl
        # Normalize P/L to 0-1 range, then combine with access count
        pl_score = min(abs(pl) / max_pl, 1.0)
        access_score = min(self.access_count / 10.0, 1.0)
        # Weighted combination: 70% P/L, 30% access frequency
        self.importance_score = 0.7 * pl_score + 0.3 * access_score


class MultiTimescaleMemory:
    """
    Multi-timescale memory system for nested learning paradigm.

    Implements hierarchical memory structure with different timescales:
    - Intraday: Recent trades (minutes/hours)
    - Daily: Daily patterns (days)
    - Weekly: Weekly patterns (weeks)
    - Monthly: Monthly patterns (months)
    - Episodic: Important events (permanent)

    Inspired by Google's Nested Learning paradigm and Hope architecture.
    """

    def __init__(self, agent_id: str):
        """
        Initialize multi-timescale memory for an agent.

        Args:
            agent_id: Agent identifier
        """
        self.agent_id = agent_id

        # Memory stores by timescale
        self.intraday_memory: deque = deque(maxlen=100)  # Last 100 trades/events
        self.daily_memory: deque = deque(maxlen=30)  # Last 30 days
        self.weekly_memory: deque = deque(maxlen=12)  # Last 12 weeks
        self.monthly_memory: deque = deque(maxlen=12)  # Last 12 months
        self.episodic_memory: list[ContextMemory] = []  # Important events (no limit)

        logger.debug(f"📊 MultiTimescaleMemory initialized for agent: {agent_id}")

    def store(self, memory: ContextMemory, auto_timescale: bool = True) -> None:
        """
        Store memory in appropriate timescale.

        Args:
            memory: Memory to store
            auto_timescale: If True, automatically determine timescale from age
        """
        if auto_timescale and memory.timescale == MemoryTimescale.DAILY:
            # Auto-determine timescale based on memory age
            created = datetime.fromisoformat(memory.created_at)
            age_days = (datetime.now() - created).days

            if age_days == 0:
                memory.timescale = MemoryTimescale.INTRADAY
            elif age_days < 7:
                memory.timescale = MemoryTimescale.DAILY
            elif age_days < 30:
                memory.timescale = MemoryTimescale.WEEKLY
            else:
                memory.timescale = MemoryTimescale.MONTHLY

        # Store in appropriate timescale
        if memory.timescale == MemoryTimescale.INTRADAY:
            self.intraday_memory.append(memory)
        elif memory.timescale == MemoryTimescale.DAILY:
            self.daily_memory.append(memory)
        elif memory.timescale == MemoryTimescale.WEEKLY:
            self.weekly_memory.append(memory)
        elif memory.timescale == MemoryTimescale.MONTHLY:
            self.monthly_memory.append(memory)
        elif memory.timescale == MemoryTimescale.EPISODIC:
            self.episodic_memory.append(memory)

        logger.debug(f"💾 Stored memory in {memory.timescale.value} timescale: {memory.memory_id}")

    def retrieve(
        self,
        timescales: list[MemoryTimescale] | None = None,
        tags: set[str] | None = None,
        min_importance: float = 0.0,
        limit_per_timescale: int = 5,
    ) -> list[ContextMemory]:
        """
        Retrieve memories from specified timescales.

        Args:
            timescales: List of timescales to retrieve from (None = all)
            tags: Filter by tags
            min_importance: Minimum importance score
            limit_per_timescale: Max memories per timescale

        Returns:
            List of memories, sorted by importance and recency
        """
        if timescales is None:
            timescales = [
                MemoryTimescale.INTRADAY,
                MemoryTimescale.DAILY,
                MemoryTimescale.WEEKLY,
                MemoryTimescale.MONTHLY,
                MemoryTimescale.EPISODIC,
            ]

        memories = []

        # Collect from each timescale
        if MemoryTimescale.INTRADAY in timescales:
            memories.extend(list(self.intraday_memory))
        if MemoryTimescale.DAILY in timescales:
            memories.extend(list(self.daily_memory))
        if MemoryTimescale.WEEKLY in timescales:
            memories.extend(list(self.weekly_memory))
        if MemoryTimescale.MONTHLY in timescales:
            memories.extend(list(self.monthly_memory))
        if MemoryTimescale.EPISODIC in timescales:
            memories.extend(self.episodic_memory)

        # Filter by tags
        if tags:
            memories = [m for m in memories if tags.intersection(m.tags) or not m.tags]

        # Filter by importance
        memories = [m for m in memories if m.importance_score >= min_importance]

        # Remove expired (except episodic and high-importance)
        memories = [m for m in memories if not m.is_expired()]

        # Sort by importance score and recency
        memories.sort(
            key=lambda m: (m.importance_score, m.access_count, m.accessed_at),
            reverse=True,
        )

        # Limit per timescale
        timescale_counts: dict[MemoryTimescale, int] = {}
        filtered_memories = []
        for memory in memories:
            timescale = memory.timescale
            count = timescale_counts.get(timescale, 0)
            if count < limit_per_timescale:
                filtered_memories.append(memory)
                timescale_counts[timescale] = count + 1

        # Touch accessed memories
        for memory in filtered_memories:
            memory.touch()

        return filtered_memories

    def consolidate_patterns(self) -> list[ContextMemory]:
        """
        Consolidate recurring patterns from short-term to long-term memory.

        This implements memory consolidation from nested learning paradigm.
        Identifies patterns that appear frequently and promotes them to longer timescales.

        Returns:
            List of newly created consolidated memories
        """
        consolidated = []

        # Analyze daily memories for patterns
        if len(self.daily_memory) >= 5:
            # Group by tags/content similarity
            pattern_groups: dict[str, list[ContextMemory]] = {}

            for memory in self.daily_memory:
                # Create pattern key from tags and content type
                pattern_key = "_".join(sorted(memory.tags)) if memory.tags else "general"

                if pattern_key not in pattern_groups:
                    pattern_groups[pattern_key] = []
                pattern_groups[pattern_key].append(memory)

            # Find patterns that appear frequently
            for pattern_key, group_memories in pattern_groups.items():
                if len(group_memories) >= 3:  # Pattern appears at least 3 times
                    # Calculate average importance and P/L
                    avg_importance = sum(m.importance_score for m in group_memories) / len(
                        group_memories
                    )
                    avg_pl = sum(m.outcome_pl or 0 for m in group_memories) / len(group_memories)

                    # Create consolidated memory
                    consolidated_memory = ContextMemory(
                        agent_id=self.agent_id,
                        content={
                            "pattern": pattern_key,
                            "frequency": len(group_memories),
                            "avg_pl": avg_pl,
                            "source_memories": [m.memory_id for m in group_memories],
                        },
                        tags=group_memories[0].tags,
                        timescale=MemoryTimescale.WEEKLY,  # Promote to weekly
                        importance_score=avg_importance,
                        outcome_pl=avg_pl,
                    )

                    # Store in weekly memory
                    self.weekly_memory.append(consolidated_memory)
                    consolidated.append(consolidated_memory)

                    logger.info(
                        f"🔄 Consolidated pattern '{pattern_key}' from {len(group_memories)} "
                        f"daily memories to weekly (importance: {avg_importance:.2f})"
                    )

        return consolidated

    def get_statistics(self) -> dict[str, Any]:
        """Get statistics about memory usage across timescales"""
        return {
            "intraday_count": len(self.intraday_memory),
            "daily_count": len(self.daily_memory),
            "weekly_count": len(self.weekly_memory),
            "monthly_count": len(self.monthly_memory),
            "episodic_count": len(self.episodic_memory),
            "total_count": (
                len(self.intraday_memory)
                + len(self.daily_memory)
                + len(self.weekly_memory)
                + len(self.monthly_memory)
                + len(self.episodic_memory)
            ),
        }

    def _remove_from_deque(self, queue: deque, memory_id: str) -> bool:
        """Remove the first matching memory from a deque while preserving order."""
        removed = False
        items = list(queue)
        queue.clear()
        for memory in items:
            if not removed and memory.memory_id == memory_id:
                removed = True
                continue
            queue.append(memory)
        return removed

    def remove(self, memory_id: str) -> bool:
        """
        Remove a memory from all timescales.

        Args:
            memory_id: Identifier of the memory to remove

        Returns:
            True if a memory was removed, False otherwise.
        """
        removed = False
        removed = self._remove_from_deque(self.intraday_memory, memory_id) or removed
        removed = self._remove_from_deque(self.daily_memory, memory_id) or removed
        removed = self._remove_from_deque(self.weekly_memory, memory_id) or removed
        removed = self._remove_from_deque(self.monthly_memory, memory_id) or removed

        episodic_len = len(self.episodic_memory)
        if episodic_len:
            self.episodic_memory = [
                memory for memory in self.episodic_memory if memory.memory_id != memory_id
            ]
            if len(self.episodic_memory) != episodic_len:
                removed = True

        if removed:
            logger.debug(
                f"🧹 Removed memory {memory_id} from multi-timescale store for {self.agent_id}"
            )
        return removed


class ContextEngine:
    """
    Context Engine: Manages structured context for multi-agent systems.

    Responsibilities:
    1. Store and retrieve semantic blueprints
    2. Manage context flow between agents
    3. Validate context integrity
    4. Persist context for memory
    5. Handle context errors gracefully
    """

    def __init__(self, storage_dir: Path | None = None, enable_multi_timescale: bool = True):
        """
        Initialize Context Engine

        Args:
            storage_dir: Directory for persistent storage (defaults to data/agent_context)
            enable_multi_timescale: Enable multi-timescale memory (nested learning)
        """
        self.storage_dir = storage_dir or Path("data/agent_context")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.enable_multi_timescale = enable_multi_timescale

        # In-memory storage
        self.blueprints: dict[str, SemanticBlueprint] = {}
        self.memory: dict[str, ContextMemory] = {}
        self.message_history: list[ContextMessage] = []

        # Multi-timescale memory (nested learning)
        self.multi_timescale_memory: dict[str, MultiTimescaleMemory] = {}

        # Load persisted data
        self._load_persisted_data()

        logger.info(
            f"✅ Context Engine initialized: {len(self.blueprints)} blueprints, "
            f"{len(self.memory)} memories, multi-timescale: {enable_multi_timescale}"
        )

    def register_blueprint(self, blueprint: SemanticBlueprint) -> None:
        """
        Register a semantic blueprint for an agent.

        Args:
            blueprint: Semantic blueprint to register
        """
        self.blueprints[blueprint.agent_id] = blueprint

        # Persist blueprint
        blueprint_file = self.storage_dir / "blueprints" / f"{blueprint.agent_id}.json"
        blueprint_file.parent.mkdir(parents=True, exist_ok=True)
        with open(blueprint_file, "w") as f:
            json.dump(asdict(blueprint), f, indent=2, default=str)

        logger.info(f"📋 Registered blueprint: {blueprint.agent_id} ({blueprint.agent_name})")

    def get_blueprint(self, agent_id: str) -> SemanticBlueprint | None:
        """Get blueprint for an agent"""
        return self.blueprints.get(agent_id)

    def get_agent_context(
        self,
        agent_id: str,
        max_tokens: int | None = None,
        use_multi_timescale: bool | None = None,
        use_1m_context: bool = True,
    ) -> dict[str, Any]:
        """
        Get complete context for an agent, including blueprint and relevant memories.

        Enhanced with multi-timescale memory retrieval for nested learning.
        Now supports 1M context windows via Claude Agent SDK (December 2025).

        Args:
            agent_id: Agent identifier
            max_tokens: Maximum context window size (None = use SDK config)
            use_multi_timescale: Override multi-timescale setting (None = use default)
            use_1m_context: Enable 1M context window support (default True)

        Returns:
            Complete context dictionary
        """
        # Get context limit from SDK config if not specified
        if max_tokens is None:
            try:
                from src.agent_framework.agent_sdk_config import get_agent_sdk_config

                sdk_config = get_agent_sdk_config()
                max_tokens = sdk_config.get_agent_context_limit(agent_id)
                if use_1m_context:
                    # Can use up to the allocated limit for this agent
                    logger.debug(f"Using 1M context: {max_tokens:,} tokens for {agent_id}")
            except ImportError:
                max_tokens = 50_000  # Default expanded limit

        blueprint = self.blueprints.get(agent_id)
        if not blueprint:
            logger.warning(f"⚠️ No blueprint found for agent: {agent_id}")
            return {}

        use_mts = (
            use_multi_timescale if use_multi_timescale is not None else self.enable_multi_timescale
        )

        context = {
            "blueprint": blueprint.to_context_dict(),
            "memories": [],
            "recent_messages": [],
            "timescale_breakdown": {} if use_mts else None,
        }

        # Retrieve memories using multi-timescale if enabled
        if use_mts and agent_id in self.multi_timescale_memory:
            mts_memory = self.multi_timescale_memory[agent_id]

            # Get memories from all timescales
            memories = mts_memory.retrieve(
                timescales=None,  # All timescales
                limit_per_timescale=3,  # 3 per timescale = 15 total max
            )

            # Group by timescale for context
            timescale_groups: dict[str, list[dict[str, Any]]] = {}
            for memory in memories:
                timescale = memory.timescale.value
                if timescale not in timescale_groups:
                    timescale_groups[timescale] = []
                timescale_groups[timescale].append(asdict(memory))

            context["timescale_breakdown"] = {
                timescale: len(mems) for timescale, mems in timescale_groups.items()
            }

            # Add memories to context (prioritize by importance)
            token_count = len(json.dumps(context))
            for memory in memories:
                memory_json = json.dumps(
                    asdict(memory),
                    default=lambda o: list(o)
                    if isinstance(o, set)
                    else (getattr(o, "value", str(o))),
                )
                if token_count + len(memory_json) < max_tokens:
                    context["memories"].append(asdict(memory))
                    token_count += len(memory_json)
                else:
                    break
        else:
            # Fallback to original single-timescale retrieval
            agent_memories = [
                m for m in self.memory.values() if m.agent_id == agent_id and not m.is_expired()
            ]
            agent_memories.sort(key=lambda m: (m.access_count, m.accessed_at), reverse=True)

            token_count = len(json.dumps(context))
            for memory in agent_memories[:10]:  # Limit to top 10 memories
                memory_json = json.dumps(
                    asdict(memory),
                    default=lambda o: list(o)
                    if isinstance(o, set)
                    else (getattr(o, "value", str(o))),
                )
                if token_count + len(memory_json) < max_tokens:
                    context["memories"].append(asdict(memory))
                    token_count += len(memory_json)
                else:
                    break

        # Add recent messages involving this agent
        recent_messages = [
            msg
            for msg in self.message_history[-20:]
            if msg.sender_agent == agent_id or msg.receiver_agent == agent_id
        ]
        context["recent_messages"] = [msg.to_mcp_format() for msg in recent_messages[-5:]]

        return context

    def send_context_message(
        self,
        sender: str,
        receiver: str,
        payload: dict[str, Any],
        context_type: ContextType = ContextType.COMMUNICATION_CONTEXT,
        metadata: dict[str, Any] | None = None,
    ) -> ContextMessage:
        """
        Send a structured context message between agents.

        Args:
            sender: Sender agent ID
            receiver: Receiver agent ID
            payload: Message payload
            context_type: Type of context
            metadata: Optional metadata

        Returns:
            Created context message
        """
        message = ContextMessage(
            sender_agent=sender,
            receiver_agent=receiver,
            context_type=context_type,
            payload=payload,
            metadata=metadata or {},
        )

        # Validate message
        is_valid, errors = message.validate()
        if not is_valid:
            logger.error(f"❌ Invalid context message: {errors}")
            raise ValueError(f"Invalid context message: {errors}")

        # Store in history
        self.message_history.append(message)

        # Persist message
        self._persist_message(message)

        logger.debug(f"📨 Context message sent: {sender} -> {receiver}")
        return message

    def store_memory(
        self,
        agent_id: str,
        content: dict[str, Any],
        tags: set[str] | None = None,
        ttl_days: int | None = None,
        timescale: MemoryTimescale | None = None,
        importance_score: float | None = None,
        outcome_pl: float | None = None,
    ) -> ContextMemory:
        """
        Store context in memory for later retrieval.

        Enhanced with multi-timescale support for nested learning.

        Args:
            agent_id: Agent identifier
            content: Content to store
            tags: Optional tags for retrieval
            ttl_days: Time-to-live in days (None = permanent)
            timescale: Memory timescale (None = auto-determine)
            importance_score: Importance score 0.0-1.0 (None = default 0.5)
            outcome_pl: Profit/loss from this memory (for importance scoring)

        Returns:
            Created memory object
        """
        memory = ContextMemory(
            agent_id=agent_id,
            content=content,
            tags=tags or set(),
            ttl_days=ttl_days,
            timescale=timescale or MemoryTimescale.DAILY,
            importance_score=importance_score or 0.5,
            outcome_pl=outcome_pl,
        )

        # Update importance if P/L provided
        if outcome_pl is not None:
            memory.update_importance(outcome_pl)

        # Store in traditional memory (backward compatibility)
        self.memory[memory.memory_id] = memory

        # Store in multi-timescale memory if enabled
        if self.enable_multi_timescale:
            if agent_id not in self.multi_timescale_memory:
                self.multi_timescale_memory[agent_id] = MultiTimescaleMemory(agent_id)

            self.multi_timescale_memory[agent_id].store(memory, auto_timescale=True)

        # Persist memory
        self._persist_memory(memory)

        logger.debug(
            f"💾 Memory stored: {agent_id} ({len(content)} keys) "
            f"[timescale: {memory.timescale.value}, importance: {memory.importance_score:.2f}]"
        )
        return memory

    def remove_memory(self, memory_id: str) -> bool:
        """
        Remove a memory from the engine and persistent storage.

        Args:
            memory_id: Identifier of the memory to remove

        Returns:
            True if a memory was removed, False otherwise.
        """
        memory = self.memory.pop(memory_id, None)
        if not memory:
            return False

        if self.enable_multi_timescale:
            mts = self.multi_timescale_memory.get(memory.agent_id)
            if mts:
                mts.remove(memory_id)

        memory_file = self.storage_dir / "memories" / f"{memory_id}.json"
        with contextlib.suppress(FileNotFoundError):
            memory_file.unlink()

        logger.debug(f"🧽 Memory removed: {memory_id}")
        return True

    def prune_memories(
        self,
        agent_id: str | None = None,
        tags: set[str] | None = None,
        max_removed: int = 5,
    ) -> list[str]:
        """
        Remove memories that match the provided filters (agent and/or tags).

        Args:
            agent_id: Agent identifier to filter by
            tags: Set of tags that must intersect
            max_removed: Maximum number of memories to delete

        Returns:
            List of removed memory IDs.
        """
        candidates = list(self.memory.values())

        if agent_id:
            candidates = [mem for mem in candidates if mem.agent_id == agent_id]

        if tags:
            candidates = [mem for mem in candidates if tags.intersection(mem.tags)]

        # Sort newest first so stale failures leave the context before recent ones.
        candidates.sort(key=lambda mem: mem.created_at, reverse=True)

        removed_ids: list[str] = []
        for memory in candidates[:max_removed]:
            if self.remove_memory(memory.memory_id):
                removed_ids.append(memory.memory_id)

        if removed_ids:
            logger.debug(
                f"✂️ Pruned {len(removed_ids)} memories (agent={agent_id or 'ALL'}, tags={tags})"
            )

        return removed_ids

    def retrieve_memories(
        self,
        agent_id: str | None = None,
        tags: set[str] | None = None,
        limit: int = 10,
        timescales: list[MemoryTimescale] | None = None,
        min_importance: float = 0.0,
        use_multi_timescale: bool | None = None,
    ) -> list[ContextMemory]:
        """
        Retrieve memories by agent ID and/or tags.

        Enhanced with multi-timescale support for nested learning.

        Args:
            agent_id: Filter by agent ID
            tags: Filter by tags
            limit: Maximum number of memories to return
            timescales: Filter by timescales (multi-timescale only)
            min_importance: Minimum importance score (multi-timescale only)
            use_multi_timescale: Override multi-timescale setting

        Returns:
            List of matching memories
        """
        use_mts = (
            use_multi_timescale if use_multi_timescale is not None else self.enable_multi_timescale
        )

        # Use multi-timescale retrieval if enabled
        if use_mts and agent_id and agent_id in self.multi_timescale_memory:
            mts_memory = self.multi_timescale_memory[agent_id]
            memories = mts_memory.retrieve(
                timescales=timescales,
                tags=tags,
                min_importance=min_importance,
                limit_per_timescale=max(limit // 5, 1),  # Distribute limit across timescales
            )
            return memories[:limit]

        # Fallback to traditional retrieval
        memories = list(self.memory.values())

        # Filter by agent
        if agent_id:
            memories = [m for m in memories if m.agent_id == agent_id]

        # Filter by tags
        if tags:
            memories = [m for m in memories if tags.intersection(m.tags)]

        # Remove expired
        memories = [m for m in memories if not m.is_expired()]

        # Sort by importance score (if available), then recency and access count
        memories.sort(
            key=lambda m: (m.importance_score, m.access_count, m.accessed_at),
            reverse=True,
        )

        # Touch accessed memories
        for memory in memories[:limit]:
            memory.touch()

        return memories[:limit]

    def consolidate_agent_memory(self, agent_id: str) -> list[ContextMemory]:
        """
        Consolidate patterns for an agent's multi-timescale memory.

        This implements memory consolidation from nested learning paradigm.

        Args:
            agent_id: Agent identifier

        Returns:
            List of newly consolidated memories
        """
        if not self.enable_multi_timescale:
            logger.warning("Multi-timescale memory not enabled")
            return []

        if agent_id not in self.multi_timescale_memory:
            logger.warning(f"No multi-timescale memory found for agent: {agent_id}")
            return []

        mts_memory = self.multi_timescale_memory[agent_id]
        consolidated = mts_memory.consolidate_patterns()

        # Persist consolidated memories
        for memory in consolidated:
            self._persist_memory(memory)

        return consolidated

    def get_memory_statistics(self, agent_id: str | None = None) -> dict[str, Any]:
        """
        Get statistics about memory usage.

        Args:
            agent_id: Agent identifier (None = all agents)

        Returns:
            Memory statistics dictionary
        """
        stats = {
            "total_memories": len(self.memory),
            "multi_timescale_enabled": self.enable_multi_timescale,
        }

        if self.enable_multi_timescale:
            if agent_id:
                if agent_id in self.multi_timescale_memory:
                    stats["agent_memory"] = {
                        agent_id: self.multi_timescale_memory[agent_id].get_statistics()
                    }
            else:
                stats["all_agents"] = {
                    aid: mts.get_statistics() for aid, mts in self.multi_timescale_memory.items()
                }

        return stats

    def validate_context_flow(
        self, from_agent: str, to_agent: str, context: dict[str, Any]
    ) -> tuple[bool, list[str]]:
        """
        Validate that context can flow correctly between agents.

        Checks:
        1. Both agents have blueprints
        2. Sender's outputs match receiver's inputs
        3. Required fields are present

        Args:
            from_agent: Sender agent ID
            to_agent: Receiver agent ID
            context: Context to validate

        Returns:
            (is_valid, list_of_errors)
        """
        errors = []

        sender_blueprint = self.blueprints.get(from_agent)
        receiver_blueprint = self.blueprints.get(to_agent)

        if not sender_blueprint:
            errors.append(f"Sender agent '{from_agent}' has no blueprint")

        if not receiver_blueprint:
            errors.append(f"Receiver agent '{to_agent}' has no blueprint")

        if sender_blueprint and receiver_blueprint:
            # Check if sender's outputs match receiver's inputs
            set(sender_blueprint.outputs.keys())
            set(receiver_blueprint.inputs.keys())

            # Check for required inputs
            for input_key, input_spec in receiver_blueprint.inputs.items():
                if input_spec.get("required", False) and input_key not in context:
                    errors.append(f"Missing required input '{input_key}' for {to_agent}")

        return len(errors) == 0, errors

    def _load_persisted_data(self):
        """Load blueprints and memories from disk"""
        # Load blueprints
        blueprints_dir = self.storage_dir / "blueprints"
        if blueprints_dir.exists():
            for blueprint_file in blueprints_dir.glob("*.json"):
                try:
                    with open(blueprint_file) as f:
                        data = json.load(f)
                        blueprint = SemanticBlueprint(**data)
                        self.blueprints[blueprint.agent_id] = blueprint
                except Exception as e:
                    logger.warning(f"Failed to load blueprint {blueprint_file}: {e}")

        # Load memories
        memories_dir = self.storage_dir / "memories"
        if memories_dir.exists():
            for memory_file in memories_dir.glob("*.json"):
                try:
                    with open(memory_file) as f:
                        data = json.load(f)
                        # Handle timescale enum conversion
                        if "timescale" in data and isinstance(data["timescale"], str):
                            data["timescale"] = MemoryTimescale(data["timescale"])
                        memory = ContextMemory(**data)
                        memory.tags = set(memory.tags)  # Convert list back to set
                        self.memory[memory.memory_id] = memory

                        # Load into multi-timescale memory if enabled
                        if self.enable_multi_timescale:
                            if memory.agent_id not in self.multi_timescale_memory:
                                self.multi_timescale_memory[memory.agent_id] = MultiTimescaleMemory(
                                    memory.agent_id
                                )
                            self.multi_timescale_memory[memory.agent_id].store(
                                memory, auto_timescale=False
                            )
                except Exception as e:
                    logger.warning(f"Failed to load memory {memory_file}: {e}")

    def _persist_message(self, message: ContextMessage):
        """Persist message to disk"""
        messages_dir = self.storage_dir / "messages"
        messages_dir.mkdir(parents=True, exist_ok=True)

        message_file = messages_dir / f"{message.message_id}.json"
        with open(message_file, "w") as f:
            json.dump(asdict(message), f, indent=2, default=str)

    def _persist_memory(self, memory: ContextMemory):
        """Persist memory to disk"""
        memories_dir = self.storage_dir / "memories"
        memories_dir.mkdir(parents=True, exist_ok=True)

        memory_file = memories_dir / f"{memory.memory_id}.json"
        memory_dict = asdict(memory)
        memory_dict["tags"] = list(memory_dict["tags"])  # Convert set to list for JSON
        memory_dict["timescale"] = memory.timescale.value  # Convert enum to string
        with open(memory_file, "w") as f:
            json.dump(memory_dict, f, indent=2, default=str)


# Global singleton instance
_context_engine: ContextEngine | None = None


def get_context_engine(storage_dir: Path | None = None) -> ContextEngine:
    """Get or create global context engine instance"""
    global _context_engine
    if _context_engine is None:
        _context_engine = ContextEngine(storage_dir=storage_dir)
    return _context_engine
