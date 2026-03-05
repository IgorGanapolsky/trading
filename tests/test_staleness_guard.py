"""Tests for src/utils/staleness_guard.py"""

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from src.utils.staleness_guard import (
    ContextFreshnessResult,
    ContextFreshnessSource,
    DataIntegrityResult,
    StalenessResult,
    check_data_staleness,
    check_context_freshness,
    require_fresh_data,
    require_fresh_context,
    get_staleness_warning,
    validate_system_state,
    check_data_integrity,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_state(tmp_path: Path, data: dict) -> Path:
    """Write a system_state.json in tmp_path and return its path."""
    p = tmp_path / "system_state.json"
    p.write_text(json.dumps(data))
    return p


def _fresh_state(hours_ago: float = 1.0) -> dict:
    """Return a minimal valid state dict with a timestamp `hours_ago` hours in the past."""
    ts = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "meta": {"last_updated": ts},
        "portfolio": {"equity": "100500.00", "cash": "80000.00"},
        "paper_account": {"positions_count": 0, "positions": []},
    }


# ===========================================================================
# check_data_staleness
# ===========================================================================


class TestCheckDataStaleness:
    def test_fresh_data_is_not_stale(self, tmp_path):
        p = _write_state(tmp_path, _fresh_state(hours_ago=1.0))
        result = check_data_staleness(state_path=p)
        assert not result.is_stale
        assert not result.blocking
        assert result.hours_old < 2.0
        assert result.last_updated is not None

    def test_stale_data_on_market_day_blocks(self, tmp_path):
        p = _write_state(tmp_path, _fresh_state(hours_ago=30.0))
        result = check_data_staleness(state_path=p, is_market_day=True)
        assert result.is_stale
        assert result.blocking
        assert result.hours_old > 24.0

    def test_stale_data_on_non_market_day_does_not_block(self, tmp_path):
        p = _write_state(tmp_path, _fresh_state(hours_ago=30.0))
        result = check_data_staleness(state_path=p, is_market_day=False)
        assert result.is_stale
        assert not result.blocking

    def test_custom_max_stale_hours(self, tmp_path):
        p = _write_state(tmp_path, _fresh_state(hours_ago=5.0))
        result = check_data_staleness(state_path=p, max_stale_hours=4.0)
        assert result.is_stale

    def test_missing_file(self, tmp_path):
        p = tmp_path / "nonexistent.json"
        result = check_data_staleness(state_path=p)
        assert result.is_stale
        assert math.isinf(result.hours_old)
        assert result.last_updated is None
        assert "does not exist" in result.reason

    def test_missing_file_non_market_day(self, tmp_path):
        p = tmp_path / "nonexistent.json"
        result = check_data_staleness(state_path=p, is_market_day=False)
        assert result.is_stale
        assert not result.blocking

    def test_invalid_json(self, tmp_path):
        p = tmp_path / "system_state.json"
        p.write_text("NOT JSON{{{")
        result = check_data_staleness(state_path=p)
        assert result.is_stale
        assert "invalid JSON" in result.reason

    def test_missing_last_updated_field(self, tmp_path):
        p = _write_state(tmp_path, {"portfolio": {}, "paper_account": {}})
        result = check_data_staleness(state_path=p)
        assert result.is_stale
        assert "no last_updated" in result.reason

    def test_top_level_last_updated_fallback(self, tmp_path):
        """When meta.last_updated is absent, top-level last_updated is used."""
        ts = (datetime.now(timezone.utc) - timedelta(hours=0.5)).strftime("%Y-%m-%dT%H:%M:%SZ")
        state = {"last_updated": ts, "portfolio": {}, "paper_account": {}}
        p = _write_state(tmp_path, state)
        result = check_data_staleness(state_path=p)
        assert not result.is_stale

    def test_non_iso_timestamp_format(self, tmp_path):
        """Supports '%Y-%m-%d %H:%M:%S' format."""
        ts = (datetime.now(timezone.utc) - timedelta(hours=2.0)).strftime("%Y-%m-%d %H:%M:%S")
        state = {"meta": {"last_updated": ts}, "portfolio": {}, "paper_account": {}}
        p = _write_state(tmp_path, state)
        result = check_data_staleness(state_path=p)
        assert not result.is_stale
        assert result.hours_old < 3.0

    def test_result_is_staleness_result_dataclass(self, tmp_path):
        p = _write_state(tmp_path, _fresh_state())
        result = check_data_staleness(state_path=p)
        assert isinstance(result, StalenessResult)


# ===========================================================================
# require_fresh_data
# ===========================================================================


class TestRequireFreshData:
    def test_fresh_data_returns_true(self):
        fresh = StalenessResult(
            is_stale=False,
            hours_old=1.0,
            last_updated="2026-01-01T00:00:00Z",
            reason="Data is fresh",
            blocking=False,
        )
        with patch("src.utils.staleness_guard.check_data_staleness", return_value=fresh):
            assert require_fresh_data(is_market_day=True) is True

    def test_stale_blocking_raises_runtime_error(self):
        stale = StalenessResult(
            is_stale=True,
            hours_old=30.0,
            last_updated="2025-12-01T00:00:00Z",
            reason="Data is 30.0 hours old",
            blocking=True,
        )
        with patch("src.utils.staleness_guard.check_data_staleness", return_value=stale):
            with pytest.raises(RuntimeError, match="Trading blocked"):
                require_fresh_data(is_market_day=True)

    def test_stale_non_blocking_returns_true(self):
        stale_no_block = StalenessResult(
            is_stale=True,
            hours_old=30.0,
            last_updated="2025-12-01T00:00:00Z",
            reason="Data is 30.0 hours old",
            blocking=False,
        )
        with patch("src.utils.staleness_guard.check_data_staleness", return_value=stale_no_block):
            assert require_fresh_data(is_market_day=False) is True


# ===========================================================================
# get_staleness_warning
# ===========================================================================


class TestGetStalenessWarning:
    def test_returns_none_when_fresh(self):
        fresh = StalenessResult(
            is_stale=False,
            hours_old=1.0,
            last_updated="2026-01-01T00:00:00Z",
            reason="Data is fresh",
            blocking=False,
        )
        with patch("src.utils.staleness_guard.check_data_staleness", return_value=fresh):
            assert get_staleness_warning() is None

    def test_returns_warning_string_when_stale(self):
        stale = StalenessResult(
            is_stale=True,
            hours_old=30.0,
            last_updated="2025-12-01T00:00:00Z",
            reason="Data is 30.0 hours old",
            blocking=False,
        )
        with patch("src.utils.staleness_guard.check_data_staleness", return_value=stale):
            warning = get_staleness_warning()
            assert warning is not None
            assert "STALE" in warning

    def test_never_blocks(self):
        """get_staleness_warning always passes is_market_day=False internally."""
        stale = StalenessResult(
            is_stale=True,
            hours_old=float("inf"),
            last_updated=None,
            reason="system_state.json does not exist",
            blocking=False,
        )
        with patch("src.utils.staleness_guard.check_data_staleness", return_value=stale):
            warning = get_staleness_warning()
            assert warning is not None


# ===========================================================================
# Context freshness SLO checks
# ===========================================================================


class TestContextFreshness:
    def test_check_context_freshness_stale_when_index_missing(self, tmp_path, monkeypatch):
        missing_rag = tmp_path / "missing_lessons_query.json"
        missing_context = tmp_path / "missing_context_index.json"
        monkeypatch.setattr("src.utils.staleness_guard.RAG_QUERY_INDEX_PATH", missing_rag)
        monkeypatch.setattr("src.utils.staleness_guard.CONTEXT_INDEX_PATH", missing_context)

        result = check_context_freshness(is_market_day=True)
        assert result.is_stale
        assert result.blocking
        assert "rag_query_index" in result.stale_sources
        assert "context_engine_index" in result.stale_sources

    def test_check_context_freshness_passes_when_indexes_are_fresh(self, tmp_path, monkeypatch):
        rag_path = tmp_path / "lessons_query.json"
        context_path = tmp_path / "context_index.json"

        rag_path.write_text(
            json.dumps(
                [
                    {
                        "id": "ll_1",
                        "indexed_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    }
                ]
            ),
            encoding="utf-8",
        )
        context_path.write_text(
            json.dumps({"built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}),
            encoding="utf-8",
        )
        monkeypatch.setattr("src.utils.staleness_guard.RAG_QUERY_INDEX_PATH", rag_path)
        monkeypatch.setattr("src.utils.staleness_guard.CONTEXT_INDEX_PATH", context_path)
        monkeypatch.setenv("RAG_QUERY_INDEX_MAX_AGE_MINUTES", "120")
        monkeypatch.setenv("CONTEXT_INDEX_MAX_AGE_MINUTES", "120")

        result = check_context_freshness(is_market_day=True)
        assert not result.is_stale
        assert not result.blocking

    def test_check_context_freshness_handles_timezone_offsets(self, tmp_path, monkeypatch):
        rag_path = tmp_path / "lessons_query.json"
        context_path = tmp_path / "context_index.json"

        now_utc = datetime.now(timezone.utc)
        ten_minutes_ago_utc = now_utc - timedelta(minutes=10)
        offset_ts = ten_minutes_ago_utc.astimezone(timezone(timedelta(hours=-5))).isoformat()

        rag_path.write_text(
            json.dumps([{"id": "ll_tz", "indexed_at_utc": offset_ts}]),
            encoding="utf-8",
        )
        context_path.write_text(
            json.dumps({"built_at": offset_ts}),
            encoding="utf-8",
        )
        monkeypatch.setattr("src.utils.staleness_guard.RAG_QUERY_INDEX_PATH", rag_path)
        monkeypatch.setattr("src.utils.staleness_guard.CONTEXT_INDEX_PATH", context_path)
        monkeypatch.setenv("RAG_QUERY_INDEX_MAX_AGE_MINUTES", "30")
        monkeypatch.setenv("CONTEXT_INDEX_MAX_AGE_MINUTES", "30")

        result = check_context_freshness(is_market_day=True)
        assert not result.is_stale
        assert not result.blocking

    def test_require_fresh_context_raises_when_blocking(self):
        stale = ContextFreshnessResult(
            is_stale=True,
            blocking=True,
            checked_at="2026-01-01T00:00:00Z",
            stale_sources=["rag_query_index"],
            sources=[
                ContextFreshnessSource(
                    source="rag_query_index",
                    path="data/rag/lessons_query.json",
                    last_sync=None,
                    age_minutes=float("inf"),
                    max_age_minutes=60.0,
                    is_stale=True,
                    reason="missing",
                )
            ],
            reason="stale context",
        )
        with patch("src.utils.staleness_guard.check_context_freshness", return_value=stale):
            with pytest.raises(RuntimeError, match="stale context"):
                require_fresh_context(is_market_day=True)

    def test_require_fresh_context_non_blocking_returns_true(self):
        stale = ContextFreshnessResult(
            is_stale=True,
            blocking=False,
            checked_at="2026-01-01T00:00:00Z",
            stale_sources=["rag_query_index"],
            sources=[],
            reason="stale context",
        )
        with patch("src.utils.staleness_guard.check_context_freshness", return_value=stale):
            assert require_fresh_context(is_market_day=False) is True


# ===========================================================================
# validate_system_state
# ===========================================================================


class TestValidateSystemState:
    def test_valid_state(self, tmp_path):
        p = _write_state(tmp_path, _fresh_state())
        result = validate_system_state(state_path=p)
        assert result.is_valid
        assert result.errors == []

    def test_missing_file(self, tmp_path):
        p = tmp_path / "nonexistent.json"
        result = validate_system_state(state_path=p)
        assert not result.is_valid
        assert any("does not exist" in e for e in result.errors)

    def test_invalid_json(self, tmp_path):
        p = tmp_path / "system_state.json"
        p.write_text("{broken")
        result = validate_system_state(state_path=p)
        assert not result.is_valid
        assert any("Invalid JSON" in e for e in result.errors)

    def test_missing_required_fields(self, tmp_path):
        p = _write_state(tmp_path, {"foo": "bar"})
        result = validate_system_state(state_path=p)
        assert not result.is_valid
        assert any("portfolio" in e for e in result.errors)
        assert any("paper_account" in e for e in result.errors)

    def test_zero_equity_is_invalid(self, tmp_path):
        state = {
            "portfolio": {"equity": "0", "cash": "1000"},
            "paper_account": {"positions_count": 0, "positions": []},
        }
        p = _write_state(tmp_path, state)
        result = validate_system_state(state_path=p)
        assert not result.is_valid
        assert any("equity" in e.lower() for e in result.errors)

    def test_negative_cash_is_invalid(self, tmp_path):
        state = {
            "portfolio": {"equity": "100000", "cash": "-500"},
            "paper_account": {"positions_count": 0, "positions": []},
        }
        p = _write_state(tmp_path, state)
        result = validate_system_state(state_path=p)
        assert not result.is_valid
        assert any("cash" in e.lower() for e in result.errors)

    def test_positions_count_mismatch_warns(self, tmp_path):
        state = {
            "portfolio": {"equity": "100000", "cash": "80000"},
            "paper_account": {
                "positions_count": 3,
                "positions": [{"symbol": "SPY", "price": "450.00"}],
            },
        }
        p = _write_state(tmp_path, state)
        result = validate_system_state(state_path=p)
        # Count mismatch is a warning, not an error
        assert result.is_valid
        assert any("mismatch" in w.lower() for w in result.warnings)

    def test_position_missing_symbol_is_error(self, tmp_path):
        state = {
            "portfolio": {"equity": "100000", "cash": "80000"},
            "paper_account": {
                "positions_count": 1,
                "positions": [{"price": "450.00"}],
            },
        }
        p = _write_state(tmp_path, state)
        result = validate_system_state(state_path=p)
        assert not result.is_valid
        assert any("missing symbol" in e for e in result.errors)

    def test_position_negative_price_is_error(self, tmp_path):
        state = {
            "portfolio": {"equity": "100000", "cash": "80000"},
            "paper_account": {
                "positions_count": 1,
                "positions": [{"symbol": "SPY", "price": "-10"}],
            },
        }
        p = _write_state(tmp_path, state)
        result = validate_system_state(state_path=p)
        assert not result.is_valid
        assert any("negative price" in e for e in result.errors)

    def test_large_equity_drift_warns(self, tmp_path):
        state = {
            "portfolio": {"equity": "200000", "cash": "150000"},
            "paper_account": {"positions_count": 0, "positions": []},
        }
        p = _write_state(tmp_path, state)
        result = validate_system_state(state_path=p)
        assert result.is_valid
        assert any("drift" in w.lower() for w in result.warnings)

    def test_small_equity_drift_no_warning(self, tmp_path):
        state = {
            "portfolio": {"equity": "105000", "cash": "80000"},
            "paper_account": {"positions_count": 0, "positions": []},
        }
        p = _write_state(tmp_path, state)
        result = validate_system_state(state_path=p)
        assert result.is_valid
        assert not any("drift" in w.lower() for w in result.warnings)

    def test_result_is_data_integrity_dataclass(self, tmp_path):
        p = _write_state(tmp_path, _fresh_state())
        result = validate_system_state(state_path=p)
        assert isinstance(result, DataIntegrityResult)

    def test_empty_positions_list(self, tmp_path):
        state = {
            "portfolio": {"equity": "100000", "cash": "80000"},
            "paper_account": {"positions_count": 0, "positions": []},
        }
        p = _write_state(tmp_path, state)
        result = validate_system_state(state_path=p)
        assert result.is_valid
        assert result.errors == []

    def test_positions_at_top_level_fallback(self, tmp_path):
        """Positions can live at top level if not under paper_account."""
        state = {
            "portfolio": {"equity": "100000", "cash": "80000"},
            "paper_account": {"positions_count": 1},
            "positions": [{"symbol": "SPY", "price": "450"}],
        }
        p = _write_state(tmp_path, state)
        result = validate_system_state(state_path=p)
        assert result.is_valid


# ===========================================================================
# check_data_integrity
# ===========================================================================


class TestCheckDataIntegrity:
    def test_returns_true_for_valid_state(self):
        valid = DataIntegrityResult(is_valid=True, errors=[], warnings=[])
        with patch("src.utils.staleness_guard.validate_system_state", return_value=valid):
            assert check_data_integrity() is True

    def test_returns_false_when_errors(self):
        invalid = DataIntegrityResult(
            is_valid=False,
            errors=["system_state.json does not exist"],
            warnings=[],
        )
        with patch("src.utils.staleness_guard.validate_system_state", return_value=invalid):
            assert check_data_integrity() is False

    def test_returns_true_with_warnings_only(self):
        warned = DataIntegrityResult(
            is_valid=True,
            errors=[],
            warnings=["Large equity drift: 25.0% from initial $100000.0"],
        )
        with patch("src.utils.staleness_guard.validate_system_state", return_value=warned):
            assert check_data_integrity() is True
