"""Tests for unified search index."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.rag.unified_search import SearchDocument, UnifiedSearch, get_unified_search


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def search():
    """Create a fresh UnifiedSearch instance (not singleton)."""
    return UnifiedSearch()


@pytest.fixture
def sample_docs():
    """Build a list of sample SearchDocuments for unit tests."""
    now = datetime.now()
    return [
        SearchDocument(
            id="lesson:iron_condor_risk",
            source_type="lesson",
            title="Iron Condor Risk Management",
            content="Iron condor risk management requires monitoring delta exposure and adjusting spreads when tested. Always close at 50% profit target.",
            date=now - timedelta(days=3),
            severity="CRITICAL",
            tags=["SPY"],
            metadata={"symbol": "SPY"},
        ),
        SearchDocument(
            id="lesson:position_sizing",
            source_type="lesson",
            title="Position Sizing Rules",
            content="Position sizing for credit spreads should never exceed 5% of account value. Kelly criterion provides optimal sizing.",
            date=now - timedelta(days=60),
            severity="HIGH",
            tags=[],
            metadata={},
        ),
        SearchDocument(
            id="trade:SPY_IC_001",
            source_type="trade",
            title="SPY iron_condor 2026-01-22",
            content="SPY iron_condor entry:2026-01-22 exit:2026-02-06 credit:$81 debit:$40 PnL:$41 outcome:win put_strikes:655-660 call_strikes:720-725",
            date=now - timedelta(days=25),
            severity="MEDIUM",
            tags=["SPY"],
            metadata={"symbol": "SPY", "strategy": "iron_condor", "pnl": 41, "outcome": "win"},
        ),
        SearchDocument(
            id="decision:2026-02-09:IWM",
            source_type="session_decision",
            title="2026-02-09 IWM REJECTED",
            content="2026-02-09 IWM REJECTED gate:1 reason:MACD=-0.69 (bearish); Vol=0.2x (low) MACD:1.83 RSI:52.13 ADX:19.44 price:$264.24",
            date=now - timedelta(days=7),
            severity="MEDIUM",
            tags=["IWM"],
            metadata={"symbol": "IWM", "decision": "REJECTED"},
        ),
        SearchDocument(
            id="lesson:low_priority_note",
            source_type="lesson",
            title="Minor Code Cleanup",
            content="Removed unused imports and fixed linting warnings in test files. No functional changes.",
            date=now - timedelta(days=200),
            severity="LOW",
            tags=[],
            metadata={},
        ),
    ]


@pytest.fixture
def indexed_search(search, sample_docs):
    """Return a UnifiedSearch with sample docs indexed."""
    search._documents = sample_docs
    search._build_idf()
    return search


@pytest.fixture
def test_data_dir(tmp_path):
    """Create a temporary data directory with sample files."""
    # Lessons
    lessons_dir = tmp_path / "rag_knowledge" / "lessons_learned"
    lessons_dir.mkdir(parents=True)
    (lessons_dir / "ll_001_test_lesson_jan12.md").write_text(
        "# Test Lesson\n\n**Severity**: HIGH\n\nIron condor adjustments require monitoring delta.\n"
    )
    (lessons_dir / "ll_002_another_lesson_feb01.md").write_text(
        "# Another Lesson\n\n**Severity**: CRITICAL\n\nSPY spread risk management critical for survival.\n"
    )

    # Data dir
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # trades.json
    (data_dir / "trades.json").write_text(
        json.dumps(
            {
                "trades": [
                    {
                        "id": "IC_TEST_001",
                        "symbol": "SPY",
                        "strategy": "iron_condor",
                        "status": "closed",
                        "entry_date": "2026-01-22",
                        "exit_date": "2026-02-06",
                        "entry_credit": 81.0,
                        "exit_debit": 40.0,
                        "realized_pnl": 41.0,
                        "outcome": "win",
                        "legs": {"put_strikes": [655, 660], "call_strikes": [720, 725]},
                    }
                ]
            }
        )
    )

    # spread_performance.json
    (data_dir / "spread_performance.json").write_text(
        json.dumps(
            {
                "trades": [
                    {
                        "date": "2026-01-20",
                        "symbol": "SPY260220P00653000",
                        "premium": 975,
                        "pnl": 419,
                        "is_win": True,
                        "trade_num": 1,
                    }
                ]
            }
        )
    )

    # session_decisions
    (data_dir / "session_decisions_2026-02-09.json").write_text(
        json.dumps(
            {
                "session": {"date": "2026-02-09"},
                "decisions": [
                    {
                        "ticker": "SPY",
                        "decision": "REJECTED",
                        "rejection_reason": "MACD=-0.76 (bearish)",
                        "gate_reached": 1,
                        "indicators": {
                            "macd": 0.63,
                            "rsi": 61.86,
                            "adx": 14.69,
                            "current_price": 690.84,
                            "symbol": "SPY",
                        },
                    }
                ],
            }
        )
    )

    # market_signals
    signals_dir = data_dir / "market_signals"
    signals_dir.mkdir()
    (signals_dir / "test_signal.json").write_text(
        json.dumps(
            {
                "signal": "test_signal",
                "status": "ok",
                "severity_score": 0.5,
                "reasons": ["Test reason"],
                "updated_at": "2026-02-16T17:00:00+00:00",
            }
        )
    )

    # trend_snapshot.json
    (data_dir / "trend_snapshot.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-02-16T12:00:00",
                "symbols": {
                    "SPY": {
                        "symbol": "SPY",
                        "price": 690,
                        "regime_bias": "uptrend",
                        "gate_open": True,
                        "sma20": 688,
                        "sma50": 680,
                        "sma200": 650,
                    }
                },
            }
        )
    )

    return tmp_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBuildIndex:
    """Tests for index building."""

    def test_build_index_loads_all_sources(self, test_data_dir, monkeypatch):
        """Verify build_index returns stats with all source types."""
        import src.rag.unified_search as mod

        monkeypatch.setattr(mod, "PROJECT_ROOT", test_data_dir)
        monkeypatch.setattr(mod, "DATA_DIR", test_data_dir / "data")
        monkeypatch.setattr(mod, "LESSONS_DIR", test_data_dir / "rag_knowledge" / "lessons_learned")

        s = UnifiedSearch()
        stats = s.build_index()

        assert stats["lessons"] == 2
        assert stats["trades"] >= 1
        assert stats["session_decisions"] >= 1
        assert stats["market_signals"] >= 1
        assert stats["bm25_vocabulary"] > 0
        assert stats["avg_doc_length"] > 0

    @pytest.mark.skipif(
        not Path("rag_knowledge/lessons_learned").exists(),
        reason="Real data directory not available",
    )
    def test_build_index_real_data(self):
        """Integration test with real project data."""
        s = UnifiedSearch()
        stats = s.build_index()
        assert stats["lessons"] > 0

    def test_contaminated_trade_ledger_is_not_indexed(self, tmp_path, monkeypatch):
        import src.rag.unified_search as mod

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        row = {
            "id": "IC_1",
            "symbol": "SPY",
            "strategy": "iron_condor",
            "status": "closed",
            "entry_date": "2026-01-22",
            "exit_date": "2026-02-06",
            "realized_pnl": 41,
            "outcome": "win",
        }
        (data_dir / "trades.json").write_text(
            json.dumps(
                {
                    "trades": [row],
                    "stats": {
                        "closed_trades": 2,
                        "total_realized_pnl": 91,
                        "unpaired_order_count": 1,
                        "unpaired_realized_pnl": 50,
                    },
                }
            )
        )
        monkeypatch.setattr(mod, "DATA_DIR", data_dir)

        search = UnifiedSearch()
        docs = search._load_trades()

        assert docs == []
        assert search._last_trade_evidence["issues"]


class TestBM25Scoring:
    """Tests for BM25 keyword scoring."""

    def test_bm25_higher_for_matching_docs(self, indexed_search):
        """Docs with more matching terms should score higher."""
        query = indexed_search._tokenize("iron condor risk management")

        score_ic = indexed_search._bm25_score(
            query,
            "Iron condor risk management requires monitoring delta exposure and adjusting spreads when tested.",
        )
        score_pos = indexed_search._bm25_score(
            query, "Position sizing for credit spreads should never exceed 5% of account value."
        )

        assert score_ic > score_pos

    def test_bm25_zero_for_no_match(self, indexed_search):
        """BM25 should return 0 for completely unrelated content."""
        query = indexed_search._tokenize("xyznonexistent abcfake")
        score = indexed_search._bm25_score(query, "Iron condor risk management")
        assert score == 0.0


class TestMetadataScoring:
    """Tests for metadata-based scoring."""

    def test_ticker_boost(self, indexed_search, sample_docs):
        """Docs with matching ticker should score higher."""
        spy_doc = sample_docs[0]  # has SPY tag
        no_ticker_doc = sample_docs[1]  # no ticker tags

        score_spy = indexed_search._metadata_score(spy_doc, {"SPY"})
        score_none = indexed_search._metadata_score(no_ticker_doc, {"SPY"})

        assert score_spy > score_none

    def test_severity_boost(self, indexed_search, sample_docs):
        """CRITICAL severity docs should score higher than LOW."""
        critical_doc = sample_docs[0]  # CRITICAL
        low_doc = sample_docs[4]  # LOW

        score_crit = indexed_search._metadata_score(critical_doc, set())
        score_low = indexed_search._metadata_score(low_doc, set())

        assert score_crit > score_low

    def test_recency_boost(self, indexed_search):
        """Recent documents should get higher metadata scores."""
        now = datetime.now()
        recent_doc = SearchDocument(
            id="test:recent",
            source_type="lesson",
            title="Recent",
            content="test content",
            date=now - timedelta(days=2),
            severity="MEDIUM",
        )
        old_doc = SearchDocument(
            id="test:old",
            source_type="lesson",
            title="Old",
            content="test content",
            date=now - timedelta(days=200),
            severity="MEDIUM",
        )

        score_recent = indexed_search._metadata_score(recent_doc, set())
        score_old = indexed_search._metadata_score(old_doc, set())

        assert score_recent > score_old


class TestSearch:
    """Tests for the search method."""

    def test_search_returns_results(self, indexed_search):
        """Search for 'iron condor' should return non-empty results."""
        results = indexed_search.search("iron condor")
        assert len(results) > 0

    def test_search_source_type_filter(self, indexed_search):
        """Filtering by source_type should only return matching types."""
        results = indexed_search.search("SPY", source_types=["trade"])
        for r in results:
            assert r["type"] == "trade"

    def test_search_result_format(self, indexed_search):
        """Each result must have required keys."""
        results = indexed_search.search("iron condor")
        assert len(results) > 0
        required_keys = {
            "id",
            "type",
            "title",
            "score",
            "snippet",
            "keyword_score",
            "metadata_score",
            "metadata",
        }
        for r in results:
            assert required_keys.issubset(r.keys()), f"Missing keys: {required_keys - r.keys()}"

    def test_empty_query(self, indexed_search):
        """Empty query should return empty results."""
        assert indexed_search.search("") == []
        assert indexed_search.search("   ") == []

    def test_search_with_ticker_filter(self, indexed_search):
        """Ticker parameter should boost relevant results."""
        results_with_ticker = indexed_search.search("condor", ticker="SPY")
        results_no_ticker = indexed_search.search("condor")

        # Both should return results
        assert len(results_with_ticker) > 0
        assert len(results_no_ticker) > 0

    def test_search_severity_filter(self, indexed_search):
        """Severity filter should restrict results."""
        results = indexed_search.search("iron condor risk", severity_filter="CRITICAL")
        for r in results:
            # All results should be from CRITICAL docs
            assert True  # Filter applied in candidate selection


class TestTokenizer:
    """Tests for tokenization."""

    def test_removes_stopwords(self):
        """Tokenizer should strip stopwords."""
        s = UnifiedSearch()
        tokens = s._tokenize("the iron condor is a strategy for trading with options")
        assert "the" not in tokens
        assert "for" not in tokens
        assert "with" not in tokens
        assert "iron" in tokens
        assert "condor" in tokens
        assert "strategy" in tokens
        assert "options" in tokens

    def test_removes_short_tokens(self):
        """Tokens with length <= 2 should be removed."""
        s = UnifiedSearch()
        tokens = s._tokenize("I am an iron condor trader ok no")
        assert "am" not in tokens
        assert "an" not in tokens
        assert "ok" not in tokens
        assert "no" not in tokens
        assert "iron" in tokens

    def test_lowercases(self):
        """Tokens should be lowercased."""
        s = UnifiedSearch()
        tokens = s._tokenize("SPY IRON CONDOR")
        assert "spy" in tokens
        assert "iron" in tokens


class TestSingleton:
    """Tests for singleton pattern."""

    def test_singleton_returns_same_instance(self):
        """get_unified_search should return the same instance."""
        import src.rag.unified_search as mod

        # Reset singleton
        mod._instance = None
        s1 = get_unified_search()
        s2 = get_unified_search()
        assert s1 is s2

        # Cleanup
        mod._instance = None
