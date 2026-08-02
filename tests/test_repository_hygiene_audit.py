from scripts.audit_repository_hygiene import lesson_id, normalize_lesson_id, physical_line_count


def test_physical_line_count_handles_empty_and_missing_newline() -> None:
    assert physical_line_count(b"") == 0
    assert physical_line_count(b"one\n") == 1
    assert physical_line_count(b"one\ntwo") == 2


def test_normalize_and_extract_lesson_id() -> None:
    assert normalize_lesson_id("ll_0280") == "LL-280"
    assert lesson_id("rag_knowledge/lessons_learned/ll_999_wrong.md", "---\nid: LL-327\n---\n") == "LL-327"
    assert lesson_id("rag_knowledge/lessons_learned/ll_327_title.md", "# Title") == "LL-327"
