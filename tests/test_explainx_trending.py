"""Honest ExplainX trending ingest: parsed scores, mapped rails, two ceilings."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.core.active_strategy import StrategyKillState
from src.core.trading_profiles import get_put_credit_profile
from src.intel.explainx.ceilings import (
    COHORT_GATE_N,
    FORBIDDEN_RESETS,
    build_ceiling_report,
    count_put_credit_cohort,
)
from src.intel.explainx.harness_split import classify_command
from src.intel.explainx.map_rails import LOOKALIKE_SNIPPETS, lookalike_hits, map_items
from src.intel.explainx.parse import (
    UNAVAILABLE,
    ExplainXParseError,
    _assert_http_url,
    parse_trending_html,
)

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests/fixtures/explainx/trending_snippet.html"
ADAPTER = REPO / "src/intel/explainx"
OPS = REPO / "scripts/explainx_trending.py"


def test_fixture_parses_ranked_scores_not_invented() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    items = parse_trending_html(html)
    assert len(items) >= 10
    assert items[0].rank == 1
    assert items[0].score == 925
    assert "limit-reset" in items[0].name.lower()
    scores = [item.score for item in items]
    assert scores == sorted(scores, reverse=True)
    assert all(isinstance(item.score, int) for item in items)


def test_empty_html_is_unavailable() -> None:
    assert parse_trending_html("") == []
    assert parse_trending_html("<html><body>no items</body></html>") == []
    assert UNAVAILABLE == "UNAVAILABLE"


def test_live_rsc_double_quoted_push_still_parses() -> None:
    html = (
        '<script>self.__next_f.push([1,"30:[[\\"$\\",\\"$L36\\",null,'
        '{\\"items\\":[{\\"type\\":\\"blog\\",\\"name\\":\\"Limit Reset\\",'
        '\\"href\\":\\"/blog/limit-reset\\",\\"score\\":925}]}]"])</script>'
    )
    items = parse_trending_html(html)
    assert len(items) == 1
    assert items[0].score == 925
    assert items[0].name == "Limit Reset"


def test_map_limit_reset_and_commerce_and_never_auto_install() -> None:
    items = parse_trending_html(FIXTURE.read_text(encoding="utf-8"))
    mapped = {row["name"]: row for row in map_items(items)}
    limit_row = next(row for row in mapped.values() if "limit-reset" in row["name"].lower())
    assert limit_row["disposition"] == "implement"
    assert limit_row["rail"] == "two_ceiling_honesty"
    assert limit_row["auto_install"] is False

    commerce = next(row for row in mapped.values() if "commerce" in row["name"].lower())
    assert commerce["disposition"] == "implement"
    assert commerce["rail"] == "planner_executor_split"
    assert commerce["auto_install"] is False

    workshop = next(row for row in mapped.values() if row["type"] == "workshop")
    assert workshop["disposition"] == "skip"
    assert workshop["auto_install"] is False

    satellite = next(row for row in mapped.values() if "god" in row["name"].lower())
    assert satellite["disposition"] == "skip"
    assert satellite["rail"] is None


def test_show_me_and_grill_me_map_without_install() -> None:
    items = parse_trending_html(FIXTURE.read_text(encoding="utf-8"))
    mapped = map_items(items)
    show = next(row for row in mapped if "show-me" in row["name"].lower())
    assert show["disposition"] == "implement"
    assert show["rail"] == "evidence_json_cli"
    assert show["auto_install"] is False
    grill = next(row for row in mapped if "grill-me" in row["name"].lower())
    assert grill["disposition"] == "map_existing"
    assert grill["rail"] == "judge_panel"
    assert grill["auto_install"] is False


def test_cli_fixture_json_ok() -> None:
    completed = subprocess.run(
        [sys.executable, str(OPS), "--fixture", str(FIXTURE)],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["n"] >= 10
    assert payload["auto_install"] is False
    assert payload["explainx_score_is_not_trading_roi"] is True
    assert payload["mapped"][0]["score"] == 925


def test_cli_empty_fixture_fails_closed(tmp_path: Path) -> None:
    empty = tmp_path / "empty.html"
    empty.write_text("<html></html>", encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(OPS), "--fixture", str(empty)],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )
    assert completed.returncode == 2
    payload = json.loads(completed.stdout)
    assert payload["ok"] is False
    assert payload["status"] == UNAVAILABLE


def test_two_ceilings_daily_reset_does_not_raise_cohort() -> None:
    profile = get_put_credit_profile()
    kill = StrategyKillState(
        active_family="spy_put_credit",
        killed_families=("ic_simple", "iron_condor"),
        reason="test",
        successor="spy_put_credit",
        paper_only=True,
        live_blocked=True,
    )
    now = datetime(2026, 9, 4, tzinfo=UTC)
    entries = {
        "a": {"entry_time": "2026-09-04T12:00:00+00:00"},
        "b": {"entry_time": "2026-09-03T12:00:00+00:00"},
    }
    trades = [
        {"strategy": "iron_condor", "status": "closed"},
        {"strategy": "spy_put_credit", "status": "closed"},
        {"strategy": "spy_put_credit", "status": "closed"},
        {"strategy": "spy_put_credit", "status": "closed"},
    ]
    report = build_ceiling_report(
        profile=profile,
        kill_state=kill,
        entries=entries,
        trades=trades,
        now=now,
    )
    assert report["session_analog"]["cap"] == 3
    assert report["session_analog"]["used"] == 1
    assert report["weekly_analog"]["used"] == 3
    assert report["weekly_analog"]["cap"] == COHORT_GATE_N
    assert report["resetting_session_increases_weekly"] is False
    assert report["live_blocked"] is True
    assert report["live_unblocked"] is False
    assert "reset-weekly" in report["forbidden_resets"]
    # Mixing killed IC into cohort n is the lie this report exists to prevent.
    assert count_put_credit_cohort(trades) == 3
    assert count_put_credit_cohort(trades) != 4


def test_forbidden_resets_named() -> None:
    assert "reset-weekly" in FORBIDDEN_RESETS
    assert "reset-kill-switch" in FORBIDDEN_RESETS


def test_planner_dry_run_vs_executor_vs_denied() -> None:
    plan = classify_command("python scripts/spy_put_credit.py --dry-run")
    assert plan["role"] == "planner"
    assert plan["allowed"] is True
    assert plan["eval"] == "plan_quality_not_fill"
    assert plan["vendor_conversion_figures_are_ours"] is False

    exe = classify_command("python scripts/spy_put_credit.py")
    assert exe["role"] == "executor"
    assert exe["commerce_analog"] == "merchant_agent"
    assert exe["allowed"] is True
    assert exe["eval"] == "policy_accuracy_not_conversion"

    live = classify_command("python scripts/spy_put_credit.py --live")
    assert live["allowed"] is False
    assert live["role"] == "denied"

    mixed = classify_command("python scripts/spy_put_credit.py --dry-run --live")
    assert mixed["allowed"] is False
    assert mixed["role"] == "denied"

    denied = classify_command("close_position SPY")
    assert denied["role"] == "denied"
    assert denied["allowed"] is False

    invented = classify_command("/reset-weekly")
    assert invented["role"] == "denied"
    assert invented["allowed"] is False


def test_malformed_score_does_not_crash() -> None:
    html = (
        '<script>self.__next_f.push([1,"{\\"items\\":['
        '{\\"name\\":\\"Bad\\",\\"href\\":\\"/x\\",\\"score\\":\\"nope\\",\\"type\\":\\"blog\\"},'
        '{\\"name\\":\\"Good\\",\\"href\\":\\"/y\\",\\"score\\":10,\\"type\\":\\"blog\\"}'
        ']}"])</script>'
    )
    items = parse_trending_html(html)
    assert len(items) == 1
    assert items[0].name == "Good"
    assert items[0].score == 10


def test_brackets_in_title_do_not_truncate_items() -> None:
    html = (
        '<script>self.__next_f.push([1,"{\\"items\\":['
        '{\\"name\\":\\"Foo [bar]\\",\\"href\\":\\"/a\\",\\"score\\":3,\\"type\\":\\"blog\\"},'
        '{\\"name\\":\\"Baz\\",\\"href\\":\\"/b\\",\\"score\\":2,\\"type\\":\\"blog\\"}'
        ']}"])</script>'
    )
    items = parse_trending_html(html)
    assert [item.name for item in items] == ["Foo [bar]", "Baz"]


def test_statusless_rows_are_not_closed_cohort() -> None:
    trades = [
        {"strategy": "spy_put_credit", "status": "closed"},
        {"strategy": "spy_put_credit", "status": ""},
        {"strategy": "spy_put_credit"},
        {"strategy": "spy_put_credit", "status": "open"},
    ]
    assert count_put_credit_cohort(trades) == 1


def test_transport_rejects_non_http_schemes() -> None:
    with pytest.raises(ExplainXParseError):
        _assert_http_url("file:///etc/passwd")
    with pytest.raises(ExplainXParseError):
        _assert_http_url("ftp://explainx.ai/trending")


def test_sources_are_not_the_mac_yolo_theater_engine() -> None:
    blobs = [OPS.read_text(encoding="utf-8")]
    for path in ADAPTER.glob("*.py"):
        if path.name == "map_rails.py":
            continue
        blobs.append(path.read_text(encoding="utf-8"))
    joined = "\n".join(blobs)
    hits = lookalike_hits(joined)
    assert hits == [], hits
    # The map module may name the theater only as a refusal list.
    assert "tf-idf vectorization" in LOOKALIKE_SNIPPETS
