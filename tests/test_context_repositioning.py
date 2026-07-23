from src.rag.context_repositioning import reposition_lessons


def test_performance_query_prioritizes_verified_trade_evidence(monkeypatch):
    monkeypatch.setenv("CONTEXT_REPOSITIONING", "true")
    lessons = [
        {
            "id": "generic_story",
            "title": "Trading reflections",
            "content": "A broad narrative about markets and automation.",
            "score": 1.8,
            "severity": "LOW",
        },
        {
            "id": "verified_trade_evidence_latest",
            "title": "Verified trade evidence",
            "content": (
                "Metric unit: paired_closed_structure. "
                "Profit factor, expectancy, and inventory attribution are audited."
            ),
            "score": 0.1,
            "severity": "CRITICAL",
        },
    ]

    ranked = reposition_lessons(
        "Why are we losing money and missing the north star?",
        lessons,
        top_k=2,
    )

    assert ranked[0]["id"] == "verified_trade_evidence_latest"


def test_non_performance_query_does_not_apply_evidence_override(monkeypatch):
    monkeypatch.setenv("CONTEXT_REPOSITIONING", "true")
    lessons = [
        {
            "id": "entry_timing",
            "title": "Entry timing",
            "content": "Market open timing guidance.",
            "score": 1.5,
            "severity": "LOW",
        },
        {
            "id": "verified_trade_evidence_latest",
            "title": "Verified trade evidence",
            "content": "paired_closed_structure profit factor",
            "score": 0.0,
            "severity": "LOW",
        },
    ]

    ranked = reposition_lessons("When does the market open?", lessons, top_k=2)

    assert ranked[0]["id"] == "entry_timing"
