from pathlib import Path


RAG_QUERY_HTML = Path("docs/rag-query.html")


def test_rag_query_has_published_sql_analytics_sources() -> None:
    html = RAG_QUERY_HTML.read_text(encoding="utf-8")

    assert "const SQL_ANALYTICS_SUMMARY_URL" in html
    assert "const SQL_ANALYTICS_SUMMARY_FALLBACK_URL" in html
    assert "async function fetchSqlAnalyticsSummary(forceReload = false)" in html


def test_rag_query_handles_period_over_period_analytics_questions() -> None:
    html = RAG_QUERY_HTML.read_text(encoding="utf-8")

    assert "function isSqlAnalyticsQuery(message)" in html
    assert "function buildSqlAnalyticsEvidenceHtml(summary)" in html
    assert "fetchSqlAnalyticsSummary(true)" in html
    assert "Period-over-period analytics" in html
    assert "period over period|day over day|week over week" in html
