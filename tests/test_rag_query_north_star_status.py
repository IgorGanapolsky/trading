from pathlib import Path


RAG_QUERY_HTML = Path("docs/rag-query.html")


def test_rag_query_replaces_static_account_status_copy() -> None:
    html = RAG_QUERY_HTML.read_text(encoding="utf-8")

    assert "function computeNorthStarStatus(state)" in html
    assert "North Star status now:" in html
    assert "Account status now:</strong> paper strategy remains the primary engine" not in html


def test_north_star_strategy_response_uses_live_state() -> None:
    html = RAG_QUERY_HTML.read_text(encoding="utf-8")

    assert "function buildNorthStarStrategyHtml(state)" in html
    assert "const state = await fetchSystemState(true);" in html
    assert "North Star is ${status.verdict}" in html


def test_rag_query_surface_has_explicit_as_of_timestamp_labels() -> None:
    html = RAG_QUERY_HTML.read_text(encoding="utf-8")

    assert 'id="ragAsOfText"' in html
    assert 'id="systemAsOfText"' in html
    assert 'id="ragAsOfTextChat"' in html
    assert 'id="systemAsOfTextChat"' in html
    assert "function parseTimestampDetails(raw)" in html
    assert "function updateAsOfText(id, prefix, details)" in html
    assert "function renderTimestampMetric(label, raw)" in html


def test_rag_query_chat_has_local_fallback_for_no_results() -> None:
    html = RAG_QUERY_HTML.read_text(encoding="utf-8")

    assert "function findLocalLessonsForChat(query, maxResults = 5)" in html
    assert "function buildLocalLessonFallbackReply(query, matches)" in html
    assert "KEY LESSONS (local_fallback):" in html
    assert "No lessons available for this query" in html


def test_rag_query_last_question_hint_shows_timestamp_not_keyboard_copy() -> None:
    html = RAG_QUERY_HTML.read_text(encoding="utf-8")

    assert "function formatChatHistoryTimestamp(raw)" in html
    assert 'class="hint-time"' in html
    assert "(click to insert, or press ↑)" not in html
