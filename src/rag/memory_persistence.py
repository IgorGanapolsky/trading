"""
Anthropic-style Memory Persistence System

Based on Claude Agent SDK patterns for maintaining context across sessions.
Provides structured storage for lessons, trades, claims, and errors with
session handoff capabilities.

Inspired by:
- Anthropic's Claude Agent SDK session management
- RAG-based knowledge persistence
- Trading system state management

Key Features:
- File-based JSON storage for portability
- Automatic backup before modifications
- CRUD operations for memory categories
- Session state tracking and handoff
- Memory versioning and rollback
"""

import json
import logging
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class MemoryCategory(str, Enum):
    """Memory categories for organizing different types of experiences."""

    LESSONS = "lessons"  # What went wrong and how to fix
    TRADES = "trades"  # Trading decisions and outcomes
    CLAIMS = "claims"  # Claims made and their verification status
    ERRORS = "errors"  # Errors encountered and resolutions
    SESSIONS = "sessions"  # Session state and handoff information


@dataclass
class MemoryEntry:
    """Individual memory entry with metadata."""

    id: str
    category: MemoryCategory
    timestamp: str
    title: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    severity: Optional[str] = None  # CRITICAL, HIGH, MEDIUM, LOW
    verified: bool = False
    session_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        # Convert enum to string
        data["category"] = (
            self.category.value if isinstance(self.category, MemoryCategory) else self.category
        )
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryEntry":
        """Create MemoryEntry from dictionary."""
        # Convert category string back to enum
        if "category" in data and isinstance(data["category"], str):
            data["category"] = MemoryCategory(data["category"])
        return cls(**data)


@dataclass
class SessionState:
    """Session state for handoff between sessions."""

    session_id: str
    start_time: str
    end_time: Optional[str] = None
    memories_created: int = 0
    memories_updated: int = 0
    status: str = "active"  # active, completed, error
    context: dict[str, Any] = field(default_factory=dict)
    learnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionState":
        """Create SessionState from dictionary."""
        return cls(**data)


class MemoryStore:
    """
    Anthropic-style memory persistence system.

    Provides structured storage for different memory categories with
    session tracking, automatic backups, and CRUD operations.

    Usage:
        store = MemoryStore()

        # Create memory
        lesson_id = store.create(
            category=MemoryCategory.LESSONS,
            title="Never skip verification",
            content="Claimed deployment successful without testing",
            severity="CRITICAL",
            tags=["verification", "deployment"]
        )

        # Read memory
        lesson = store.read(lesson_id)

        # Search memories
        results = store.search(category=MemoryCategory.LESSONS, tags=["verification"])

        # Update memory
        store.update(lesson_id, metadata={"fixed": True})

        # Delete memory
        store.delete(lesson_id)
    """

    def __init__(self, base_path: str = "data/memory"):
        """
        Initialize memory store.

        Args:
            base_path: Base directory for memory storage
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Create category directories
        for category in MemoryCategory:
            (self.base_path / category.value).mkdir(exist_ok=True)

        # Session tracking
        self.session_id = str(uuid4())[:8]
        self.session_start = datetime.now().isoformat()

        # Load or create session state
        self._load_or_create_session()

        logger.info(f"✅ MemoryStore initialized (session: {self.session_id})")

    def _load_or_create_session(self):
        """Load previous session or create new one."""
        sessions_file = self.base_path / "sessions.json"

        if sessions_file.exists():
            try:
                with open(sessions_file) as f:
                    sessions_data = json.load(f)
                self.previous_sessions = [
                    SessionState.from_dict(s) for s in sessions_data.get("sessions", [])
                ]
            except Exception as e:
                logger.warning(f"Failed to load sessions: {e}")
                self.previous_sessions = []
        else:
            self.previous_sessions = []

        # Create new session
        self.current_session = SessionState(
            session_id=self.session_id, start_time=self.session_start
        )

    def _backup_file(self, file_path: Path):
        """Create backup of file before modification."""
        if not file_path.exists():
            return

        backup_dir = self.base_path / "backups"
        backup_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
        backup_path = backup_dir / backup_name

        shutil.copy2(file_path, backup_path)
        logger.debug(f"Created backup: {backup_path}")

    def _get_memory_path(
        self, memory_id: str, category: Optional[MemoryCategory] = None
    ) -> Optional[Path]:
        """Get path to memory file."""
        if category:
            # Direct lookup
            memory_file = self.base_path / category.value / f"{memory_id}.json"
            return memory_file if memory_file.exists() else None

        # Search across all categories
        for cat in MemoryCategory:
            memory_file = self.base_path / cat.value / f"{memory_id}.json"
            if memory_file.exists():
                return memory_file

        return None

    def create(
        self,
        category: MemoryCategory,
        title: str,
        content: str,
        severity: Optional[str] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        verified: bool = False,
    ) -> str:
        """
        Create a new memory entry.

        Args:
            category: Memory category
            title: Short title/summary
            content: Full content
            severity: Optional severity (CRITICAL, HIGH, MEDIUM, LOW)
            tags: Optional tags for categorization
            metadata: Optional additional metadata
            verified: Whether this memory has been verified

        Returns:
            Memory ID
        """
        # Generate unique ID
        memory_id = (
            f"{category.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid4())[:8]}"
        )

        # Create memory entry
        entry = MemoryEntry(
            id=memory_id,
            category=category,
            timestamp=datetime.now().isoformat(),
            title=title,
            content=content,
            severity=severity,
            tags=tags or [],
            metadata=metadata or {},
            verified=verified,
            session_id=self.session_id,
        )

        # Save to file
        memory_file = self.base_path / category.value / f"{memory_id}.json"
        with open(memory_file, "w") as f:
            json.dump(entry.to_dict(), f, indent=2)

        # Update session stats
        self.current_session.memories_created += 1

        logger.info(f"✅ Created memory: {memory_id} ({category.value})")
        return memory_id

    def read(
        self, memory_id: str, category: Optional[MemoryCategory] = None
    ) -> Optional[MemoryEntry]:
        """
        Read a memory entry.

        Args:
            memory_id: Memory ID
            category: Optional category hint for faster lookup

        Returns:
            MemoryEntry or None if not found
        """
        memory_path = self._get_memory_path(memory_id, category)

        if not memory_path:
            logger.warning(f"Memory not found: {memory_id}")
            return None

        try:
            with open(memory_path) as f:
                data = json.load(f)
            return MemoryEntry.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to read memory {memory_id}: {e}")
            return None

    def update(
        self,
        memory_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        severity: Optional[str] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        verified: Optional[bool] = None,
        category: Optional[MemoryCategory] = None,
    ) -> bool:
        """
        Update an existing memory entry.

        Args:
            memory_id: Memory ID
            title: New title (optional)
            content: New content (optional)
            severity: New severity (optional)
            tags: New tags (optional)
            metadata: Metadata to merge (optional)
            verified: New verification status (optional)
            category: Optional category hint for faster lookup

        Returns:
            True if updated, False if not found
        """
        memory_path = self._get_memory_path(memory_id, category)

        if not memory_path:
            logger.warning(f"Memory not found for update: {memory_id}")
            return False

        # Backup before modification
        self._backup_file(memory_path)

        # Read current data
        entry = self.read(memory_id, category)
        if not entry:
            return False

        # Update fields
        if title is not None:
            entry.title = title
        if content is not None:
            entry.content = content
        if severity is not None:
            entry.severity = severity
        if tags is not None:
            entry.tags = tags
        if metadata is not None:
            entry.metadata.update(metadata)
        if verified is not None:
            entry.verified = verified

        # Save updated entry
        with open(memory_path, "w") as f:
            json.dump(entry.to_dict(), f, indent=2)

        # Update session stats
        self.current_session.memories_updated += 1

        logger.info(f"✅ Updated memory: {memory_id}")
        return True

    def delete(self, memory_id: str, category: Optional[MemoryCategory] = None) -> bool:
        """
        Delete a memory entry.

        Args:
            memory_id: Memory ID
            category: Optional category hint for faster lookup

        Returns:
            True if deleted, False if not found
        """
        memory_path = self._get_memory_path(memory_id, category)

        if not memory_path:
            logger.warning(f"Memory not found for deletion: {memory_id}")
            return False

        # Backup before deletion
        self._backup_file(memory_path)

        # Delete file
        memory_path.unlink()

        logger.info(f"✅ Deleted memory: {memory_id}")
        return True

    def search(
        self,
        category: Optional[MemoryCategory] = None,
        tags: Optional[list[str]] = None,
        severity: Optional[str] = None,
        verified: Optional[bool] = None,
        session_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[MemoryEntry]:
        """
        Search memories by criteria.

        Args:
            category: Filter by category
            tags: Filter by tags (must have at least one)
            severity: Filter by severity
            verified: Filter by verification status
            session_id: Filter by session ID
            limit: Maximum number of results

        Returns:
            List of matching MemoryEntry objects
        """
        results = []

        # Determine which categories to search
        categories = [category] if category else list(MemoryCategory)

        for cat in categories:
            if cat == MemoryCategory.SESSIONS:
                continue  # Skip sessions category in general search

            cat_dir = self.base_path / cat.value
            if not cat_dir.exists():
                continue

            for memory_file in cat_dir.glob("*.json"):
                try:
                    with open(memory_file) as f:
                        data = json.load(f)
                    entry = MemoryEntry.from_dict(data)

                    # Apply filters
                    if tags and not any(tag in entry.tags for tag in tags):
                        continue
                    if severity and entry.severity != severity:
                        continue
                    if verified is not None and entry.verified != verified:
                        continue
                    if session_id and entry.session_id != session_id:
                        continue

                    results.append(entry)

                except Exception as e:
                    logger.warning(f"Failed to read {memory_file}: {e}")

        # Sort by timestamp (newest first)
        results.sort(key=lambda x: x.timestamp, reverse=True)

        # Apply limit
        if limit:
            results = results[:limit]

        return results

    def get_recent(
        self, category: Optional[MemoryCategory] = None, limit: int = 10
    ) -> list[MemoryEntry]:
        """
        Get most recent memories.

        Args:
            category: Optional category filter
            limit: Number of results

        Returns:
            List of recent MemoryEntry objects
        """
        return self.search(category=category, limit=limit)

    def get_critical(self, category: Optional[MemoryCategory] = None) -> list[MemoryEntry]:
        """
        Get all CRITICAL severity memories.

        Args:
            category: Optional category filter

        Returns:
            List of CRITICAL MemoryEntry objects
        """
        return self.search(category=category, severity="CRITICAL")

    def get_unverified(self, category: Optional[MemoryCategory] = None) -> list[MemoryEntry]:
        """
        Get all unverified memories.

        Args:
            category: Optional category filter

        Returns:
            List of unverified MemoryEntry objects
        """
        return self.search(category=category, verified=False)

    def count(self, category: Optional[MemoryCategory] = None) -> int:
        """
        Count memories.

        Args:
            category: Optional category filter

        Returns:
            Count of memories
        """
        return len(self.search(category=category))

    def save_session(
        self, learnings: Optional[list[str]] = None, context: Optional[dict[str, Any]] = None
    ):
        """
        Save current session state for handoff.

        Args:
            learnings: List of key learnings from this session
            context: Additional context for next session
        """
        self.current_session.end_time = datetime.now().isoformat()
        self.current_session.status = "completed"

        if learnings:
            self.current_session.learnings = learnings
        if context:
            self.current_session.context.update(context)

        # Append to sessions list
        all_sessions = self.previous_sessions + [self.current_session]

        # Save sessions file
        sessions_file = self.base_path / "sessions.json"
        self._backup_file(sessions_file)

        with open(sessions_file, "w") as f:
            json.dump(
                {
                    "sessions": [s.to_dict() for s in all_sessions],
                    "last_updated": datetime.now().isoformat(),
                },
                f,
                indent=2,
            )

        logger.info(f"✅ Saved session state: {self.session_id}")

    def load_previous_session(self) -> Optional[SessionState]:
        """
        Load the most recent previous session.

        Returns:
            SessionState or None if no previous sessions
        """
        if not self.previous_sessions:
            return None

        # Return most recent session
        return self.previous_sessions[-1]

    def get_session_summary(self) -> dict[str, Any]:
        """
        Get summary of current session.

        Returns:
            Dictionary with session statistics
        """
        return {
            "session_id": self.session_id,
            "start_time": self.session_start,
            "memories_created": self.current_session.memories_created,
            "memories_updated": self.current_session.memories_updated,
            "duration_minutes": (
                datetime.now() - datetime.fromisoformat(self.session_start)
            ).total_seconds()
            / 60,
            "total_memories": self.count(),
            "critical_memories": len(self.get_critical()),
            "unverified_memories": len(self.get_unverified()),
        }

    def export_category(self, category: MemoryCategory, output_file: str):
        """
        Export all memories from a category to a single JSON file.

        Args:
            category: Category to export
            output_file: Output file path
        """
        memories = self.search(category=category)

        export_data = {
            "category": category.value,
            "exported_at": datetime.now().isoformat(),
            "count": len(memories),
            "memories": [m.to_dict() for m in memories],
        }

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(export_data, f, indent=2)

        logger.info(f"✅ Exported {len(memories)} {category.value} to {output_file}")

    def import_memories(self, import_file: str) -> int:
        """
        Import memories from exported JSON file.

        Args:
            import_file: Path to import file

        Returns:
            Number of memories imported
        """
        with open(import_file) as f:
            import_data = json.load(f)

        count = 0
        for memory_data in import_data.get("memories", []):
            try:
                entry = MemoryEntry.from_dict(memory_data)

                # Save to appropriate category
                memory_file = self.base_path / entry.category.value / f"{entry.id}.json"
                with open(memory_file, "w") as f:
                    json.dump(entry.to_dict(), f, indent=2)

                count += 1
            except Exception as e:
                logger.warning(f"Failed to import memory: {e}")

        logger.info(f"✅ Imported {count} memories from {import_file}")
        return count


def get_memory_store(base_path: str = "data/memory") -> MemoryStore:
    """
    Get or create singleton MemoryStore instance.

    Args:
        base_path: Base directory for memory storage

    Returns:
        MemoryStore instance
    """
    if not hasattr(get_memory_store, "_instance"):
        get_memory_store._instance = MemoryStore(base_path)
    return get_memory_store._instance


if __name__ == "__main__":
    # Demo usage
    logging.basicConfig(level=logging.INFO)

    store = MemoryStore("data/memory")

    # Create some sample memories
    lesson_id = store.create(
        category=MemoryCategory.LESSONS,
        title="Never skip verification",
        content="Claimed deployment successful without testing. Must verify end-to-end.",
        severity="CRITICAL",
        tags=["verification", "deployment"],
        verified=True,
    )

    trade_id = store.create(
        category=MemoryCategory.TRADES,
        title="SPY iron condor loss",
        content="Lost $200 on iron condor due to VIX spike. Should use wider strikes in high IV.",
        severity="HIGH",
        tags=["options", "risk_management"],
        metadata={"pnl": -200, "symbol": "SPY", "strategy": "iron_condor"},
    )

    claim_id = store.create(
        category=MemoryCategory.CLAIMS,
        title="CI tests passing",
        content="Claimed all tests passed. Need to verify coverage thresholds, not just pass/fail.",
        severity="MEDIUM",
        tags=["testing", "verification"],
        verified=False,
    )

    # Search and display
    print("\n" + "=" * 60)
    print("CRITICAL MEMORIES:")
    print("=" * 60)
    for memory in store.get_critical():
        print(f"\n[{memory.category.value.upper()}] {memory.title}")
        print(f"Severity: {memory.severity}")
        print(f"Content: {memory.content[:100]}...")

    print("\n" + "=" * 60)
    print("UNVERIFIED CLAIMS:")
    print("=" * 60)
    for memory in store.get_unverified(category=MemoryCategory.CLAIMS):
        print(f"\n{memory.title}")
        print(f"Content: {memory.content}")

    # Session summary
    print("\n" + "=" * 60)
    print("SESSION SUMMARY:")
    print("=" * 60)
    summary = store.get_session_summary()
    for key, value in summary.items():
        print(f"{key}: {value}")

    # Save session
    store.save_session(
        learnings=[
            "Always verify claims before making them",
            "Track verification status of all claims",
            "Use memory persistence for learning across sessions",
        ],
        context={"next_steps": ["Review unverified claims", "Add more critical lessons"]},
    )

    print("\n✅ Demo complete!")
