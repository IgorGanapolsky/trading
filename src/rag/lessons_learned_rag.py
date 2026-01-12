# Lessons Learned RAG stub - original deleted in cleanup PR #1445
# Minimal implementation to prevent import errors


class LessonsLearnedRAG:
    """Stub for LessonsLearnedRAG - not used in Phil Town strategy."""

    def __init__(self, *args, **kwargs):
        self.lessons = []

    def search(self, query: str, *args, **kwargs) -> list:
        """Search lessons - returns empty list."""
        return []

    def query(self, query: str, *args, **kwargs) -> list:
        """Query lessons - returns empty list."""
        return []

    def add_lesson(self, lesson: dict, *args, **kwargs) -> bool:
        """Add lesson - returns success."""
        return True

    def get_all_lessons(self, *args, **kwargs) -> list:
        """Get all lessons - returns empty list."""
        return []
