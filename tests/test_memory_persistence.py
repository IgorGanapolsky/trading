"""
Tests for Anthropic-style memory persistence system.

Tests cover:
- CRUD operations
- Session management
- Search and filtering
- Backup functionality
- Import/export
- Edge cases
"""

import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from src.rag.memory_persistence import (
    MemoryCategory,
    MemoryEntry,
    MemoryStore,
    SessionState,
    get_memory_store,
)


@pytest.fixture
def temp_memory_dir():
    """Create temporary directory for memory storage."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def memory_store(temp_memory_dir):
    """Create fresh MemoryStore instance for each test."""
    return MemoryStore(base_path=temp_memory_dir)


class TestMemoryEntry:
    """Test MemoryEntry dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        entry = MemoryEntry(
            id="test_123",
            category=MemoryCategory.LESSONS,
            timestamp="2026-01-06T12:00:00",
            title="Test Lesson",
            content="Test content",
            severity="CRITICAL",
            tags=["test", "example"],
            verified=True,
        )

        data = entry.to_dict()

        assert data["id"] == "test_123"
        assert data["category"] == "lessons"
        assert data["severity"] == "CRITICAL"
        assert data["verified"] is True
        assert data["tags"] == ["test", "example"]

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "id": "test_123",
            "category": "lessons",
            "timestamp": "2026-01-06T12:00:00",
            "title": "Test Lesson",
            "content": "Test content",
            "severity": "CRITICAL",
            "tags": ["test"],
            "metadata": {"key": "value"},
            "verified": False,
            "session_id": "abc123",
        }

        entry = MemoryEntry.from_dict(data)

        assert entry.id == "test_123"
        assert entry.category == MemoryCategory.LESSONS
        assert entry.severity == "CRITICAL"
        assert entry.verified is False
        assert entry.metadata == {"key": "value"}


class TestSessionState:
    """Test SessionState dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        session = SessionState(
            session_id="abc123",
            start_time="2026-01-06T12:00:00",
            end_time="2026-01-06T13:00:00",
            memories_created=5,
            memories_updated=2,
            status="completed",
            learnings=["Test learning"],
        )

        data = session.to_dict()

        assert data["session_id"] == "abc123"
        assert data["memories_created"] == 5
        assert data["status"] == "completed"
        assert data["learnings"] == ["Test learning"]

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "session_id": "abc123",
            "start_time": "2026-01-06T12:00:00",
            "end_time": "2026-01-06T13:00:00",
            "memories_created": 3,
            "memories_updated": 1,
            "status": "active",
            "context": {"key": "value"},
            "learnings": [],
        }

        session = SessionState.from_dict(data)

        assert session.session_id == "abc123"
        assert session.memories_created == 3
        assert session.context == {"key": "value"}


class TestMemoryStoreInitialization:
    """Test MemoryStore initialization."""

    def test_creates_directory_structure(self, temp_memory_dir):
        """Test that all category directories are created."""
        _store = MemoryStore(base_path=temp_memory_dir)  # noqa: F841

        base_path = Path(temp_memory_dir)

        # Check all category directories exist
        for category in MemoryCategory:
            cat_dir = base_path / category.value
            assert cat_dir.exists()
            assert cat_dir.is_dir()

    def test_assigns_session_id(self, memory_store):
        """Test that session ID is assigned."""
        assert memory_store.session_id
        assert len(memory_store.session_id) == 8

    def test_creates_session_state(self, memory_store):
        """Test that session state is created."""
        assert memory_store.current_session
        assert memory_store.current_session.session_id == memory_store.session_id
        assert memory_store.current_session.status == "active"

    def test_loads_previous_sessions(self, temp_memory_dir):
        """Test loading previous sessions."""
        # Create sessions file
        sessions_file = Path(temp_memory_dir) / "sessions.json"
        sessions_data = {
            "sessions": [
                {
                    "session_id": "old_session",
                    "start_time": "2026-01-05T12:00:00",
                    "end_time": "2026-01-05T13:00:00",
                    "memories_created": 3,
                    "memories_updated": 1,
                    "status": "completed",
                    "context": {},
                    "learnings": ["Old learning"],
                }
            ]
        }
        sessions_file.write_text(json.dumps(sessions_data))

        # Create store
        store = MemoryStore(base_path=temp_memory_dir)

        assert len(store.previous_sessions) == 1
        assert store.previous_sessions[0].session_id == "old_session"


class TestMemoryStoreCRUD:
    """Test CRUD operations."""

    def test_create_memory(self, memory_store):
        """Test creating a memory entry."""
        memory_id = memory_store.create(
            category=MemoryCategory.LESSONS,
            title="Test Lesson",
            content="This is a test lesson",
            severity="HIGH",
            tags=["test", "example"],
            verified=True,
        )

        assert memory_id
        assert memory_id.startswith("lessons_")

        # Verify file exists
        memory_file = Path(memory_store.base_path) / "lessons" / f"{memory_id}.json"
        assert memory_file.exists()

        # Verify session stats updated
        assert memory_store.current_session.memories_created == 1

    def test_read_memory(self, memory_store):
        """Test reading a memory entry."""
        # Create memory
        memory_id = memory_store.create(
            category=MemoryCategory.TRADES,
            title="Test Trade",
            content="Trade content",
            metadata={"pnl": 100.0},
        )

        # Read memory
        entry = memory_store.read(memory_id)

        assert entry is not None
        assert entry.id == memory_id
        assert entry.title == "Test Trade"
        assert entry.content == "Trade content"
        assert entry.metadata["pnl"] == 100.0
        assert entry.category == MemoryCategory.TRADES

    def test_read_with_category_hint(self, memory_store):
        """Test reading with category hint for faster lookup."""
        memory_id = memory_store.create(
            category=MemoryCategory.ERRORS, title="Test Error", content="Error content"
        )

        # Read with category hint
        entry = memory_store.read(memory_id, category=MemoryCategory.ERRORS)

        assert entry is not None
        assert entry.id == memory_id

    def test_read_nonexistent_memory(self, memory_store):
        """Test reading non-existent memory returns None."""
        entry = memory_store.read("nonexistent_id")
        assert entry is None

    def test_update_memory(self, memory_store):
        """Test updating a memory entry."""
        # Create memory
        memory_id = memory_store.create(
            category=MemoryCategory.CLAIMS,
            title="Original Title",
            content="Original content",
            verified=False,
        )

        # Update memory
        success = memory_store.update(
            memory_id, title="Updated Title", content="Updated content", verified=True
        )

        assert success is True

        # Read updated memory
        entry = memory_store.read(memory_id)
        assert entry.title == "Updated Title"
        assert entry.content == "Updated content"
        assert entry.verified is True

        # Verify session stats updated
        assert memory_store.current_session.memories_updated == 1

    def test_update_metadata(self, memory_store):
        """Test updating metadata merges with existing."""
        # Create memory with metadata
        memory_id = memory_store.create(
            category=MemoryCategory.TRADES,
            title="Test",
            content="Content",
            metadata={"original": "value"},
        )

        # Update with new metadata
        memory_store.update(memory_id, metadata={"new": "value"})

        # Read and verify merge
        entry = memory_store.read(memory_id)
        assert entry.metadata == {"original": "value", "new": "value"}

    def test_update_nonexistent_memory(self, memory_store):
        """Test updating non-existent memory returns False."""
        success = memory_store.update("nonexistent_id", title="New Title")
        assert success is False

    def test_delete_memory(self, memory_store):
        """Test deleting a memory entry."""
        # Create memory
        memory_id = memory_store.create(
            category=MemoryCategory.LESSONS, title="To Delete", content="Content"
        )

        # Delete memory
        success = memory_store.delete(memory_id)
        assert success is True

        # Verify file is gone
        memory_file = Path(memory_store.base_path) / "lessons" / f"{memory_id}.json"
        assert not memory_file.exists()

        # Verify can't read deleted memory
        entry = memory_store.read(memory_id)
        assert entry is None

    def test_delete_nonexistent_memory(self, memory_store):
        """Test deleting non-existent memory returns False."""
        success = memory_store.delete("nonexistent_id")
        assert success is False


class TestMemoryStoreSearch:
    """Test search and filtering."""

    def test_search_by_category(self, memory_store):
        """Test searching by category."""
        # Create memories in different categories
        memory_store.create(category=MemoryCategory.LESSONS, title="Lesson 1", content="Content")
        memory_store.create(category=MemoryCategory.TRADES, title="Trade 1", content="Content")
        memory_store.create(category=MemoryCategory.LESSONS, title="Lesson 2", content="Content")

        # Search lessons only
        results = memory_store.search(category=MemoryCategory.LESSONS)

        assert len(results) == 2
        assert all(r.category == MemoryCategory.LESSONS for r in results)

    def test_search_by_tags(self, memory_store):
        """Test searching by tags."""
        memory_store.create(
            category=MemoryCategory.LESSONS,
            title="Lesson 1",
            content="Content",
            tags=["verification", "deployment"],
        )
        memory_store.create(
            category=MemoryCategory.LESSONS, title="Lesson 2", content="Content", tags=["testing"]
        )
        memory_store.create(
            category=MemoryCategory.LESSONS,
            title="Lesson 3",
            content="Content",
            tags=["verification", "testing"],
        )

        # Search for verification tag
        results = memory_store.search(tags=["verification"])

        assert len(results) == 2
        assert all("verification" in r.tags for r in results)

    def test_search_by_severity(self, memory_store):
        """Test searching by severity."""
        memory_store.create(
            category=MemoryCategory.LESSONS,
            title="Critical 1",
            content="Content",
            severity="CRITICAL",
        )
        memory_store.create(
            category=MemoryCategory.LESSONS, title="High 1", content="Content", severity="HIGH"
        )
        memory_store.create(
            category=MemoryCategory.LESSONS,
            title="Critical 2",
            content="Content",
            severity="CRITICAL",
        )

        # Search critical only
        results = memory_store.search(severity="CRITICAL")

        assert len(results) == 2
        assert all(r.severity == "CRITICAL" for r in results)

    def test_search_by_verified(self, memory_store):
        """Test searching by verification status."""
        memory_store.create(
            category=MemoryCategory.CLAIMS, title="Verified Claim", content="Content", verified=True
        )
        memory_store.create(
            category=MemoryCategory.CLAIMS,
            title="Unverified Claim",
            content="Content",
            verified=False,
        )

        # Search unverified
        results = memory_store.search(verified=False)

        assert len(results) == 1
        assert results[0].verified is False

    def test_search_with_limit(self, memory_store):
        """Test search limit."""
        # Create 5 memories
        for i in range(5):
            memory_store.create(
                category=MemoryCategory.LESSONS, title=f"Lesson {i}", content="Content"
            )

        # Search with limit
        results = memory_store.search(limit=3)

        assert len(results) == 3

    def test_search_returns_newest_first(self, memory_store):
        """Test that search results are sorted by timestamp (newest first)."""
        # Create memories with slight delay to ensure different timestamps
        import time

        id1 = memory_store.create(category=MemoryCategory.LESSONS, title="First", content="Content")
        time.sleep(0.01)

        id2 = memory_store.create(
            category=MemoryCategory.LESSONS, title="Second", content="Content"
        )
        time.sleep(0.01)

        id3 = memory_store.create(category=MemoryCategory.LESSONS, title="Third", content="Content")

        results = memory_store.search()

        # Most recent should be first
        assert results[0].id == id3
        assert results[1].id == id2
        assert results[2].id == id1

    def test_get_recent(self, memory_store):
        """Test getting recent memories."""
        # Create several memories
        for i in range(5):
            memory_store.create(
                category=MemoryCategory.LESSONS, title=f"Lesson {i}", content="Content"
            )

        recent = memory_store.get_recent(limit=3)

        assert len(recent) == 3

    def test_get_critical(self, memory_store):
        """Test getting critical memories."""
        memory_store.create(
            category=MemoryCategory.LESSONS,
            title="Critical 1",
            content="Content",
            severity="CRITICAL",
        )
        memory_store.create(
            category=MemoryCategory.LESSONS, title="High 1", content="Content", severity="HIGH"
        )

        critical = memory_store.get_critical()

        assert len(critical) == 1
        assert critical[0].severity == "CRITICAL"

    def test_get_unverified(self, memory_store):
        """Test getting unverified memories."""
        memory_store.create(
            category=MemoryCategory.CLAIMS, title="Unverified", content="Content", verified=False
        )
        memory_store.create(
            category=MemoryCategory.CLAIMS, title="Verified", content="Content", verified=True
        )

        unverified = memory_store.get_unverified()

        assert len(unverified) == 1
        assert unverified[0].verified is False

    def test_count(self, memory_store):
        """Test counting memories."""
        # Create memories
        memory_store.create(category=MemoryCategory.LESSONS, title="Lesson 1", content="Content")
        memory_store.create(category=MemoryCategory.TRADES, title="Trade 1", content="Content")

        # Count all
        total = memory_store.count()
        assert total == 2

        # Count by category
        lessons_count = memory_store.count(category=MemoryCategory.LESSONS)
        assert lessons_count == 1


class TestBackups:
    """Test backup functionality."""

    def test_backup_created_on_update(self, memory_store):
        """Test that backup is created before update."""
        # Create memory
        memory_id = memory_store.create(
            category=MemoryCategory.LESSONS, title="Original", content="Content"
        )

        # Update memory
        memory_store.update(memory_id, title="Updated")

        # Check backup exists
        backup_dir = Path(memory_store.base_path) / "backups"
        assert backup_dir.exists()
        backups = list(backup_dir.glob("*.json"))
        assert len(backups) > 0

    def test_backup_created_on_delete(self, memory_store):
        """Test that backup is created before delete."""
        # Create memory
        memory_id = memory_store.create(
            category=MemoryCategory.LESSONS, title="To Delete", content="Content"
        )

        # Delete memory
        memory_store.delete(memory_id)

        # Check backup exists
        backup_dir = Path(memory_store.base_path) / "backups"
        assert backup_dir.exists()
        backups = list(backup_dir.glob("*.json"))
        assert len(backups) > 0


class TestSessionManagement:
    """Test session management and handoff."""

    def test_save_session(self, memory_store):
        """Test saving session state."""
        # Create some memories
        memory_store.create(category=MemoryCategory.LESSONS, title="Lesson 1", content="Content")

        # Save session
        memory_store.save_session(learnings=["Learning 1", "Learning 2"], context={"key": "value"})

        # Check session file exists
        sessions_file = Path(memory_store.base_path) / "sessions.json"
        assert sessions_file.exists()

        # Verify content
        with open(sessions_file) as f:
            data = json.load(f)

        assert len(data["sessions"]) == 1
        session = data["sessions"][0]
        assert session["session_id"] == memory_store.session_id
        assert session["status"] == "completed"
        assert session["learnings"] == ["Learning 1", "Learning 2"]
        assert session["context"] == {"key": "value"}

    def test_load_previous_session(self, temp_memory_dir):
        """Test loading previous session."""
        # Create first session
        store1 = MemoryStore(base_path=temp_memory_dir)
        store1.create(category=MemoryCategory.LESSONS, title="Lesson 1", content="Content")
        store1.save_session(learnings=["First session learning"])

        # Create second session
        store2 = MemoryStore(base_path=temp_memory_dir)

        # Load previous
        previous = store2.load_previous_session()

        assert previous is not None
        assert previous.session_id == store1.session_id
        assert previous.learnings == ["First session learning"]

    def test_get_session_summary(self, memory_store):
        """Test getting session summary."""
        # Create and update some memories
        memory_store.create(
            category=MemoryCategory.LESSONS,
            title="Lesson 1",
            content="Content",
            severity="CRITICAL",
        )
        memory_id = memory_store.create(
            category=MemoryCategory.CLAIMS, title="Claim 1", content="Content", verified=False
        )
        memory_store.update(memory_id, verified=True)

        # Get summary
        summary = memory_store.get_session_summary()

        assert summary["session_id"] == memory_store.session_id
        assert summary["memories_created"] == 2
        assert summary["memories_updated"] == 1
        assert summary["total_memories"] == 2
        assert summary["critical_memories"] == 1
        assert "duration_minutes" in summary


class TestImportExport:
    """Test import/export functionality."""

    def test_export_category(self, memory_store, temp_memory_dir):
        """Test exporting a category."""
        # Create memories
        memory_store.create(category=MemoryCategory.LESSONS, title="Lesson 1", content="Content 1")
        memory_store.create(category=MemoryCategory.LESSONS, title="Lesson 2", content="Content 2")

        # Export
        export_file = Path(temp_memory_dir) / "export.json"
        memory_store.export_category(MemoryCategory.LESSONS, str(export_file))

        # Verify export file
        assert export_file.exists()

        with open(export_file) as f:
            data = json.load(f)

        assert data["category"] == "lessons"
        assert data["count"] == 2
        assert len(data["memories"]) == 2

    def test_import_memories(self, temp_memory_dir):
        """Test importing memories."""
        # Create export data
        export_data = {
            "category": "lessons",
            "exported_at": datetime.now().isoformat(),
            "count": 2,
            "memories": [
                {
                    "id": "imported_1",
                    "category": "lessons",
                    "timestamp": datetime.now().isoformat(),
                    "title": "Imported Lesson 1",
                    "content": "Content 1",
                    "severity": "HIGH",
                    "tags": ["imported"],
                    "metadata": {},
                    "verified": True,
                    "session_id": "old_session",
                },
                {
                    "id": "imported_2",
                    "category": "lessons",
                    "timestamp": datetime.now().isoformat(),
                    "title": "Imported Lesson 2",
                    "content": "Content 2",
                    "severity": "MEDIUM",
                    "tags": ["imported"],
                    "metadata": {},
                    "verified": False,
                    "session_id": "old_session",
                },
            ],
        }

        import_file = Path(temp_memory_dir) / "import.json"
        with open(import_file, "w") as f:
            json.dump(export_data, f)

        # Import
        store = MemoryStore(base_path=temp_memory_dir)
        count = store.import_memories(str(import_file))

        assert count == 2

        # Verify memories exist
        entry1 = store.read("imported_1")
        assert entry1 is not None
        assert entry1.title == "Imported Lesson 1"

        entry2 = store.read("imported_2")
        assert entry2 is not None
        assert entry2.title == "Imported Lesson 2"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_search(self, memory_store):
        """Test search with no results."""
        results = memory_store.search(category=MemoryCategory.LESSONS)
        assert results == []

    def test_create_with_minimal_data(self, memory_store):
        """Test creating memory with only required fields."""
        memory_id = memory_store.create(
            category=MemoryCategory.ERRORS, title="Minimal", content="Content"
        )

        entry = memory_store.read(memory_id)
        assert entry is not None
        assert entry.severity is None
        assert entry.tags == []
        assert entry.metadata == {}
        assert entry.verified is False

    def test_concurrent_session_ids(self, temp_memory_dir):
        """Test that different stores get different session IDs."""
        store1 = MemoryStore(base_path=temp_memory_dir)
        store2 = MemoryStore(base_path=temp_memory_dir)

        assert store1.session_id != store2.session_id

    def test_get_memory_path_searches_all_categories(self, memory_store):
        """Test that _get_memory_path searches all categories."""
        # Create memory
        memory_id = memory_store.create(
            category=MemoryCategory.TRADES, title="Test", content="Content"
        )

        # Get path without category hint
        path = memory_store._get_memory_path(memory_id)

        assert path is not None
        assert "trades" in str(path)


class TestSingleton:
    """Test singleton pattern."""

    def test_get_memory_store_returns_singleton(self, temp_memory_dir):
        """Test that get_memory_store returns same instance."""
        # Clear singleton
        if hasattr(get_memory_store, "_instance"):
            delattr(get_memory_store, "_instance")

        store1 = get_memory_store(base_path=temp_memory_dir)
        store2 = get_memory_store(base_path=temp_memory_dir)

        assert store1 is store2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
