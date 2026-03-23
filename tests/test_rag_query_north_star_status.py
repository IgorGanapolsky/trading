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


def test_rag_query_chat_fallback_detects_stale_temporal_lesson_queries() -> None:
    html = RAG_QUERY_HTML.read_text(encoding="utf-8")

    assert "function inferLessonTimeWindow(query)" in html
    assert "function getLatestLessonDetails()" in html
    assert "The local lesson index is stale for" in html
    assert "System sync is newer" in html
    assert "Action: sync fresh lessons and rebuild the RAG index" in html


def test_rag_query_evidence_screenshots_support_click_to_magnify() -> None:
    html = RAG_QUERY_HTML.read_text(encoding="utf-8")

    assert 'id="evidenceLightbox"' in html
    assert 'id="evidenceLightboxImage"' in html
    assert "function openEvidenceLightbox(src, caption)" in html
    assert "function setupEvidenceLightboxListeners()" in html
    assert 'data-evidence-image="true"' in html


def test_rag_query_portfolio_bar_cards_are_actionable() -> None:
    html = RAG_QUERY_HTML.read_text(encoding="utf-8")

    assert 'data-action-query="Show paper account vs brokerage status."' in html
    assert 'data-action-query="How much money did we make today and why?"' in html
    assert 'data-action-query="Show my current open positions."' in html
    assert 'data-action-query="Show nearest expiry and exit pressure."' in html
    assert 'data-action-query="Show current win rate and trade sample size."' in html
    assert "function setupPortfolioActionListeners()" in html
    assert 'function buildOpenPositionsHtml(state, focus = "positions")' in html
    assert "function buildWinRateDetailHtml(state)" in html
