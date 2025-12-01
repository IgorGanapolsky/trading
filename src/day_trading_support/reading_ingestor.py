"""StudyGuideAgent builds reading assignments & drills from book metadata."""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Set

from .models import BookResource, ReadingAssignment


class StudyGuideAgent:
    """Turns structured book metadata into focused study tasks."""

    def __init__(self, books: Sequence[BookResource]) -> None:
        self.books = list(books)

    def generate_assignments(
        self,
        *,
        focus_tags: Optional[Iterable[str]] = None,
        minutes: int = 45,
    ) -> List[ReadingAssignment]:
        if minutes <= 0:
            minutes = 30
        tag_filter: Set[str] = {tag.lower() for tag in focus_tags or []}

        def _matches(book: BookResource) -> bool:
            if not tag_filter:
                return True
            return any(tag.lower() in tag_filter for tag in book.focus_tags)

        selected_books = [book for book in self.books if _matches(book)] or self.books
        assignments: List[ReadingAssignment] = []
        total_minutes = 0

        for book in selected_books:
            for segment in book.reading_plan:
                if total_minutes >= minutes:
                    break
                assignments.append(
                    ReadingAssignment(
                        book=book.title,
                        lesson=segment.goal,
                        task=f"Read/annotate: {segment.label}",
                        minutes=segment.minutes,
                        difficulty=segment.difficulty,
                        tags=list(book.focus_tags),
                    )
                )
                total_minutes += segment.minutes
            if total_minutes >= minutes:
                break

        if not assignments:
            for book in selected_books:
                fallback = book.lessons[0] if book.lessons else None
                if fallback is None:
                    continue
                assignments.append(
                    ReadingAssignment(
                        book=book.title,
                        lesson=fallback.title,
                        task=f"Summarize lesson trigger: {fallback.trigger}",
                        minutes=25,
                        difficulty=book.difficulty,
                        tags=list(book.focus_tags),
                    )
                )
                break

        return assignments
