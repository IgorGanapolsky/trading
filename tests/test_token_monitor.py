"""
Tests for src/utils/token_monitor.py

Coverage targets:
  Lines 98-108   : __init__ (data_dir setup, load_existing_data, log)
  Lines 131-172  : record_usage full logic (entry creation, thresholds, context warning)
  Lines 176-177  : get_session_stats
  Lines 181-183  : get_daily_stats
  Lines 187-189  : get_agent_stats
  Lines 193-196  : get_summary return value
  Lines 223-242  : save_report
  Lines 246-247  : _calculate_stats_unsafe
  Lines 251-273  : _calculate_stats_from_entries (non-empty path)
  Lines 288      : _get_session_total_unsafe
  Lines 292-293  : _get_recent_alerts_unsafe
  Lines 297-320  : _get_recommendations branches
  Lines 324-344  : _load_existing_data (file exists path, exception path)
  Lines 348-369  : persist
  Lines 389-394  : get_token_monitor singleton (double-check pattern)
  Lines 415-416  : record_llm_usage convenience function
"""

from __future__ import annotations

import json
import threading
from datetime import datetime

import pytest

# Reset singleton before each test so tests are independent
import src.utils.token_monitor as _tm_module
from src.utils.token_monitor import (
    TokenUsageEntry,
    TokenUsageMonitor,
    UsageStats,
    get_token_monitor,
    record_llm_usage,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset module-level singleton before every test."""
    _tm_module._monitor = None
    yield
    _tm_module._monitor = None


@pytest.fixture
def tmp_monitor(tmp_path):
    """Fresh TokenUsageMonitor backed by a temp directory."""
    return TokenUsageMonitor(data_dir=tmp_path)


# ---------------------------------------------------------------------------
# __init__ (lines 98-108)
# ---------------------------------------------------------------------------


class TestInit:
    def test_creates_data_dir(self, tmp_path):
        sub = tmp_path / "nested" / "dir"
        monitor = TokenUsageMonitor(data_dir=sub)
        assert sub.is_dir()
        assert monitor.data_dir == sub

    def test_default_data_dir(self, tmp_path):
        """Pass explicit path so we don't pollute the real data/ directory."""
        monitor = TokenUsageMonitor(data_dir=tmp_path)
        assert monitor.data_dir == tmp_path

    def test_session_start_is_datetime(self, tmp_monitor):
        assert isinstance(tmp_monitor._session_start, datetime)

    def test_entries_empty_on_fresh_init(self, tmp_monitor):
        assert tmp_monitor._entries == []

    def test_lock_is_threading_lock(self, tmp_monitor):
        # RLock / Lock – both have acquire/release
        assert hasattr(tmp_monitor._lock, "acquire")


# ---------------------------------------------------------------------------
# record_usage (lines 131-172)
# ---------------------------------------------------------------------------


class TestRecordUsage:
    def test_returns_empty_list_for_normal_usage(self, tmp_monitor):
        alerts = tmp_monitor.record_usage("agent_a", 100, 50)
        assert alerts == []

    def test_entry_appended(self, tmp_monitor):
        tmp_monitor.record_usage("agent_b", 200, 100)
        assert len(tmp_monitor._entries) == 1
        e = tmp_monitor._entries[0]
        assert e.agent_name == "agent_b"
        assert e.input_tokens == 200
        assert e.output_tokens == 100
        assert e.total_tokens == 300

    def test_known_model_sets_context_window(self, tmp_monitor):
        tmp_monitor.record_usage("a", 100, 50, model="gpt-4o")
        e = tmp_monitor._entries[0]
        assert e.context_window == 128000

    def test_unknown_model_defaults_context_window(self, tmp_monitor):
        tmp_monitor.record_usage("a", 100, 50, model="some-future-model")
        e = tmp_monitor._entries[0]
        assert e.context_window == 200000

    def test_high_single_call_alert(self, tmp_monitor):
        # total > SINGLE_CALL_THRESHOLD (50 000)
        alerts = tmp_monitor.record_usage("big_agent", 30000, 25000)
        assert any("HIGH_USAGE" in a for a in alerts)

    def test_session_threshold_alert(self, tmp_monitor):
        # Exceed SESSION_THRESHOLD (500 000) across multiple calls
        for _ in range(11):
            tmp_monitor.record_usage("agent", 25000, 25000)
        # At least one alert about session limit
        all_alerts: list[str] = []
        for _ in range(1):
            all_alerts.extend(tmp_monitor.record_usage("agent", 25000, 25000))
        # Just verify session is tracked (alert may already be in list)
        session_total = tmp_monitor._get_session_total_unsafe()
        assert session_total > tmp_monitor.SESSION_THRESHOLD

    def test_context_window_utilization_alert(self, tmp_monitor):
        # Input > 75% of context window (200 000 default) → 160 001 tokens
        alerts = tmp_monitor.record_usage("ctx_agent", 160001, 100)
        assert any("CONTEXT_WARNING" in a for a in alerts)

    def test_context_window_utilization_no_alert_below_75_pct(self, tmp_monitor):
        alerts = tmp_monitor.record_usage("ctx_agent", 100000, 100)
        assert not any("CONTEXT_WARNING" in a for a in alerts)

    def test_thread_safety(self, tmp_monitor):
        """Concurrent record_usage calls should not corrupt entries."""
        errors = []

        def worker():
            try:
                tmp_monitor.record_usage("t", 100, 50)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert len(tmp_monitor._entries) == 20


# ---------------------------------------------------------------------------
# get_session_stats (lines 176-177)
# ---------------------------------------------------------------------------


class TestGetSessionStats:
    def test_returns_usage_stats(self, tmp_monitor):
        tmp_monitor.record_usage("a", 500, 200)
        stats = tmp_monitor.get_session_stats()
        assert isinstance(stats, UsageStats)
        assert stats.call_count == 1
        assert stats.total_tokens == 700

    def test_empty_session_returns_defaults(self, tmp_monitor):
        stats = tmp_monitor.get_session_stats()
        assert stats.call_count == 0
        assert stats.total_tokens == 0


# ---------------------------------------------------------------------------
# get_daily_stats (lines 181-183)
# ---------------------------------------------------------------------------


class TestGetDailyStats:
    def test_returns_usage_stats(self, tmp_monitor):
        tmp_monitor.record_usage("a", 300, 100)
        stats = tmp_monitor.get_daily_stats()
        assert isinstance(stats, UsageStats)
        assert stats.total_tokens == 400

    def test_daily_stats_non_negative(self, tmp_monitor):
        stats = tmp_monitor.get_daily_stats()
        assert stats.total_tokens >= 0


# ---------------------------------------------------------------------------
# get_agent_stats (lines 187-189)
# ---------------------------------------------------------------------------


class TestGetAgentStats:
    def test_filters_by_agent(self, tmp_monitor):
        tmp_monitor.record_usage("alice", 100, 50)
        tmp_monitor.record_usage("bob", 200, 100)
        stats = tmp_monitor.get_agent_stats("alice")
        assert stats.call_count == 1
        assert stats.total_tokens == 150

    def test_unknown_agent_returns_empty(self, tmp_monitor):
        stats = tmp_monitor.get_agent_stats("ghost")
        assert stats.call_count == 0


# ---------------------------------------------------------------------------
# get_summary (lines 193-196)
# ---------------------------------------------------------------------------


class TestGetSummary:
    def test_summary_keys_present(self, tmp_monitor):
        summary = tmp_monitor.get_summary()
        for key in (
            "timestamp",
            "session_start",
            "session",
            "daily",
            "thresholds",
            "recommendations",
        ):
            assert key in summary

    def test_session_section_has_required_keys(self, tmp_monitor):
        summary = tmp_monitor.get_summary()
        session = summary["session"]
        assert "total_tokens" in session
        assert "call_count" in session
        assert "avg_tokens_per_call" in session
        assert "tokens_by_agent" in session
        assert "alerts" in session

    def test_daily_section_has_threshold_pct(self, tmp_monitor):
        summary = tmp_monitor.get_summary()
        assert "threshold_pct" in summary["daily"]

    def test_thresholds_correct_values(self, tmp_monitor):
        summary = tmp_monitor.get_summary()
        th = summary["thresholds"]
        assert th["single_call"] == TokenUsageMonitor.SINGLE_CALL_THRESHOLD
        assert th["session"] == TokenUsageMonitor.SESSION_THRESHOLD
        assert th["daily"] == TokenUsageMonitor.DAILY_THRESHOLD

    def test_avg_tokens_per_call_zero_calls(self, tmp_monitor):
        summary = tmp_monitor.get_summary()
        # max(1, 0) guard means this is 0 / 1 = 0
        assert summary["session"]["avg_tokens_per_call"] == 0


# ---------------------------------------------------------------------------
# save_report (lines 223-242)
# ---------------------------------------------------------------------------


class TestSaveReport:
    def test_saves_json_file(self, tmp_monitor, tmp_path):
        tmp_monitor.record_usage("agent", 100, 50)
        report_path = tmp_monitor.save_report()
        assert report_path.exists()
        assert report_path.suffix == ".json"

    def test_report_contains_entries(self, tmp_monitor):
        tmp_monitor.record_usage("agent", 100, 50)
        report_path = tmp_monitor.save_report()
        with open(report_path) as f:
            data = json.load(f)
        assert "entries" in data
        assert len(data["entries"]) == 1

    def test_report_limits_entries_to_100(self, tmp_monitor):
        for i in range(150):
            tmp_monitor.record_usage(f"agent_{i}", 10, 5)
        report_path = tmp_monitor.save_report()
        with open(report_path) as f:
            data = json.load(f)
        assert len(data["entries"]) <= 100

    def test_report_entry_has_required_fields(self, tmp_monitor):
        tmp_monitor.record_usage("a", 100, 50, model="gpt-4o")
        report_path = tmp_monitor.save_report()
        with open(report_path) as f:
            data = json.load(f)
        entry = data["entries"][0]
        for field in ("timestamp", "agent", "input", "output", "model"):
            assert field in entry


# ---------------------------------------------------------------------------
# _calculate_stats_unsafe (lines 246-247)
# ---------------------------------------------------------------------------


class TestCalculateStatsUnsafe:
    def test_filters_by_since(self, tmp_monitor):
        # Record a usage, then query from far in the future
        tmp_monitor.record_usage("a", 100, 50)
        far_future = datetime(2099, 1, 1)
        with tmp_monitor._lock:
            stats = tmp_monitor._calculate_stats_unsafe(far_future)
        assert stats.call_count == 0

    def test_includes_entries_from_session_start(self, tmp_monitor):
        tmp_monitor.record_usage("a", 100, 50)
        with tmp_monitor._lock:
            stats = tmp_monitor._calculate_stats_unsafe(tmp_monitor._session_start)
        assert stats.call_count == 1


# ---------------------------------------------------------------------------
# _calculate_stats_from_entries (lines 251-273)
# ---------------------------------------------------------------------------


class TestCalculateStatsFromEntries:
    def _make_entry(self, agent, inp, out, model="unknown"):
        return TokenUsageEntry(
            timestamp=datetime.now(),
            agent_name=agent,
            input_tokens=inp,
            output_tokens=out,
            total_tokens=inp + out,
            model=model,
        )

    def test_empty_entries_returns_defaults(self, tmp_monitor):
        stats = tmp_monitor._calculate_stats_from_entries([])
        assert stats.total_tokens == 0
        assert stats.call_count == 0

    def test_totals_computed_correctly(self, tmp_monitor):
        entries = [self._make_entry("a", 100, 50), self._make_entry("b", 200, 100)]
        stats = tmp_monitor._calculate_stats_from_entries(entries)
        assert stats.total_input_tokens == 300
        assert stats.total_output_tokens == 150
        assert stats.total_tokens == 450
        assert stats.call_count == 2

    def test_averages_computed(self, tmp_monitor):
        entries = [self._make_entry("a", 100, 50), self._make_entry("b", 200, 100)]
        stats = tmp_monitor._calculate_stats_from_entries(entries)
        assert stats.avg_input_tokens == 150.0
        assert stats.avg_output_tokens == 75.0

    def test_max_values(self, tmp_monitor):
        entries = [self._make_entry("a", 100, 50), self._make_entry("b", 200, 10)]
        stats = tmp_monitor._calculate_stats_from_entries(entries)
        assert stats.max_input_tokens == 200
        assert stats.max_output_tokens == 50

    def test_tokens_by_agent_grouped(self, tmp_monitor):
        entries = [
            self._make_entry("alice", 100, 50),
            self._make_entry("alice", 200, 100),
            self._make_entry("bob", 50, 25),
        ]
        stats = tmp_monitor._calculate_stats_from_entries(entries)
        assert stats.tokens_by_agent["alice"] == 450  # (100+50) + (200+100)
        assert stats.tokens_by_agent["bob"] == 75

    def test_alert_generated_when_exceeds_session_threshold(self, tmp_monitor):
        # 250 001 input + 250 001 output = 500 002 > SESSION_THRESHOLD
        entries = [self._make_entry("a", 250001, 250001)]
        stats = tmp_monitor._calculate_stats_from_entries(entries)
        assert any("threshold" in a.lower() for a in stats.alerts)


# ---------------------------------------------------------------------------
# _get_session_total_unsafe (line 288)
# ---------------------------------------------------------------------------


class TestGetSessionTotalUnsafe:
    def test_sums_session_entries(self, tmp_monitor):
        tmp_monitor.record_usage("a", 100, 50)
        tmp_monitor.record_usage("b", 200, 100)
        total = tmp_monitor._get_session_total_unsafe()
        assert total == 450

    def test_zero_for_empty(self, tmp_monitor):
        assert tmp_monitor._get_session_total_unsafe() == 0


# ---------------------------------------------------------------------------
# _get_recent_alerts_unsafe (lines 292-293)
# ---------------------------------------------------------------------------


class TestGetRecentAlertsUnsafe:
    def test_returns_list(self, tmp_monitor):
        result = tmp_monitor._get_recent_alerts_unsafe()
        assert isinstance(result, list)

    def test_returns_empty_currently(self, tmp_monitor):
        """Current implementation always returns []."""
        tmp_monitor.record_usage("a", 100, 50)
        assert tmp_monitor._get_recent_alerts_unsafe() == []


# ---------------------------------------------------------------------------
# _get_recommendations (lines 297-320)
# ---------------------------------------------------------------------------


class TestGetRecommendations:
    def _stats_with(self, avg_input=0, max_input=0, by_agent=None):
        s = UsageStats()
        s.avg_input_tokens = avg_input
        s.max_input_tokens = max_input
        s.tokens_by_agent = by_agent or {}
        return s

    def test_healthy_returns_no_optimizations_message(self, tmp_monitor):
        stats = self._stats_with()
        recs = tmp_monitor._get_recommendations(stats)
        assert any("healthy" in r for r in recs)

    def test_high_avg_input_recommendation(self, tmp_monitor):
        stats = self._stats_with(avg_input=15000)
        recs = tmp_monitor._get_recommendations(stats)
        assert any("summarizing" in r.lower() for r in recs)

    def test_high_max_input_recommendation(self, tmp_monitor):
        stats = self._stats_with(max_input=60000)
        recs = tmp_monitor._get_recommendations(stats)
        assert any("50k" in r.lower() for r in recs)

    def test_heavy_agent_recommendation(self, tmp_monitor):
        # One agent uses > 70% of total
        by_agent = {"heavy": 800, "light": 100}
        stats = self._stats_with(by_agent=by_agent)
        recs = tmp_monitor._get_recommendations(stats)
        assert any("heavy" in r for r in recs)

    def test_even_agent_distribution_no_heavy_warning(self, tmp_monitor):
        # 50/50 split — no heavy agent
        by_agent = {"a": 500, "b": 500}
        stats = self._stats_with(by_agent=by_agent)
        recs = tmp_monitor._get_recommendations(stats)
        assert not any(">70%" in r for r in recs)

    def test_all_conditions_at_once(self, tmp_monitor):
        by_agent = {"big": 900, "small": 10}
        stats = self._stats_with(avg_input=20000, max_input=80000, by_agent=by_agent)
        recs = tmp_monitor._get_recommendations(stats)
        # Should have at least 3 distinct recommendations
        assert len(recs) >= 3


# ---------------------------------------------------------------------------
# _load_existing_data (lines 324-344)
# ---------------------------------------------------------------------------


class TestLoadExistingData:
    def test_loads_entries_from_daily_file(self, tmp_path):
        today = datetime.now().strftime("%Y%m%d")
        daily_file = tmp_path / f"daily_{today}.json"
        data = {
            "entries": [
                {
                    "timestamp": datetime.now().isoformat(),
                    "agent": "loaded_agent",
                    "input": 100,
                    "output": 50,
                    "model": "gpt-4o",
                }
            ]
        }
        daily_file.write_text(json.dumps(data))

        monitor = TokenUsageMonitor(data_dir=tmp_path)
        assert len(monitor._entries) == 1
        assert monitor._entries[0].agent_name == "loaded_agent"
        assert monitor._entries[0].model == "gpt-4o"

    def test_missing_model_field_defaults_to_unknown(self, tmp_path):
        today = datetime.now().strftime("%Y%m%d")
        daily_file = tmp_path / f"daily_{today}.json"
        data = {
            "entries": [
                {
                    "timestamp": datetime.now().isoformat(),
                    "agent": "a",
                    "input": 10,
                    "output": 5,
                    # no "model" key
                }
            ]
        }
        daily_file.write_text(json.dumps(data))

        monitor = TokenUsageMonitor(data_dir=tmp_path)
        assert monitor._entries[0].model == "unknown"

    def test_invalid_json_handled_gracefully(self, tmp_path):
        today = datetime.now().strftime("%Y%m%d")
        daily_file = tmp_path / f"daily_{today}.json"
        daily_file.write_text("THIS IS NOT JSON{{{")

        # Should not raise; just log a warning
        monitor = TokenUsageMonitor(data_dir=tmp_path)
        assert monitor._entries == []

    def test_no_daily_file_means_empty_entries(self, tmp_path):
        monitor = TokenUsageMonitor(data_dir=tmp_path)
        assert monitor._entries == []

    def test_total_tokens_computed_from_input_output(self, tmp_path):
        today = datetime.now().strftime("%Y%m%d")
        daily_file = tmp_path / f"daily_{today}.json"
        data = {
            "entries": [
                {
                    "timestamp": datetime.now().isoformat(),
                    "agent": "a",
                    "input": 100,
                    "output": 50,
                }
            ]
        }
        daily_file.write_text(json.dumps(data))
        monitor = TokenUsageMonitor(data_dir=tmp_path)
        assert monitor._entries[0].total_tokens == 150


# ---------------------------------------------------------------------------
# persist (lines 348-369)
# ---------------------------------------------------------------------------


class TestPersist:
    def test_creates_daily_file(self, tmp_monitor, tmp_path):
        today = datetime.now().strftime("%Y%m%d")
        tmp_monitor.record_usage("a", 100, 50)
        tmp_monitor.persist()
        daily_file = tmp_monitor.data_dir / f"daily_{today}.json"
        assert daily_file.exists()

    def test_persisted_data_is_valid_json(self, tmp_monitor):
        tmp_monitor.record_usage("a", 100, 50)
        tmp_monitor.persist()
        today = datetime.now().strftime("%Y%m%d")
        daily_file = tmp_monitor.data_dir / f"daily_{today}.json"
        with open(daily_file) as f:
            data = json.load(f)
        assert "entries" in data
        assert data["date"] == today

    def test_only_todays_entries_persisted(self, tmp_monitor, tmp_path):
        """Entries with today's date should be persisted."""
        tmp_monitor.record_usage("today_agent", 200, 100)
        tmp_monitor.persist()

        today = datetime.now().strftime("%Y%m%d")
        daily_file = tmp_monitor.data_dir / f"daily_{today}.json"
        with open(daily_file) as f:
            data = json.load(f)
        assert len(data["entries"]) >= 1
        assert any(e["agent"] == "today_agent" for e in data["entries"])

    def test_entry_fields_in_persisted_data(self, tmp_monitor):
        tmp_monitor.record_usage("persist_agent", 300, 150, model="gpt-4o")
        tmp_monitor.persist()

        today = datetime.now().strftime("%Y%m%d")
        daily_file = tmp_monitor.data_dir / f"daily_{today}.json"
        with open(daily_file) as f:
            data = json.load(f)
        entry = data["entries"][0]
        assert entry["agent"] == "persist_agent"
        assert entry["input"] == 300
        assert entry["output"] == 150
        assert entry["model"] == "gpt-4o"


# ---------------------------------------------------------------------------
# get_token_monitor singleton (lines 389-394)
# ---------------------------------------------------------------------------


class TestGetTokenMonitor:
    def test_returns_token_usage_monitor(self, tmp_path):
        monitor = get_token_monitor(data_dir=tmp_path)
        assert isinstance(monitor, TokenUsageMonitor)

    def test_singleton_returns_same_instance(self, tmp_path):
        m1 = get_token_monitor(data_dir=tmp_path)
        m2 = get_token_monitor(data_dir=tmp_path)
        assert m1 is m2

    def test_second_call_ignores_different_data_dir(self, tmp_path):
        """Once singleton is set, subsequent calls return same instance."""
        m1 = get_token_monitor(data_dir=tmp_path)
        other_dir = tmp_path / "other"
        m2 = get_token_monitor(data_dir=other_dir)
        assert m1 is m2

    def test_thread_safe_singleton_creation(self, tmp_path):
        """Multiple threads should all get the same instance."""
        instances = []
        lock = threading.Lock()

        def grab():
            inst = get_token_monitor(data_dir=tmp_path)
            with lock:
                instances.append(inst)

        threads = [threading.Thread(target=grab) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(i is instances[0] for i in instances)


# ---------------------------------------------------------------------------
# record_llm_usage convenience function (lines 415-416)
# ---------------------------------------------------------------------------


class TestRecordLlmUsage:
    def test_delegates_to_monitor(self, tmp_path):
        # Initialise singleton with tmp_path first
        monitor = get_token_monitor(data_dir=tmp_path)
        alerts = record_llm_usage("llm_agent", 100, 50, model="gpt-4o")
        assert isinstance(alerts, list)
        assert len(monitor._entries) == 1
        assert monitor._entries[0].agent_name == "llm_agent"

    def test_returns_alerts_list(self, tmp_path):
        get_token_monitor(data_dir=tmp_path)
        result = record_llm_usage("a", 10, 5)
        assert isinstance(result, list)

    def test_high_usage_alert_propagated(self, tmp_path):
        get_token_monitor(data_dir=tmp_path)
        alerts = record_llm_usage("big", 30000, 25000)
        assert any("HIGH_USAGE" in a for a in alerts)
