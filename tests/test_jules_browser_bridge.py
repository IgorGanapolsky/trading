"""Tests for scripts/jules_browser_bridge.py."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch


from scripts.jules_browser_bridge import (
    build_parser,
    check_jules_health,
    dispatch_suggestion,
    execute_chrome_js,
    expand_suggestion,
    list_jules_suggestions,
    list_recent_sessions,
    main,
)


def test_build_parser_subcommands():
    parser = build_parser()

    # Health
    args = parser.parse_args(["health"])
    assert args.command == "health"

    # List
    args = parser.parse_args(["list", "--filter", "performance", "--json"])
    assert args.command == "list"
    assert args.filter == "performance"
    assert args.json is True

    # Show
    args = parser.parse_args(["show", "12", "--json"])
    assert args.command == "show"
    assert args.index == 12
    assert args.json is True

    # Start
    args = parser.parse_args(["start", "7", "--instructions", "Do not break tests"])
    assert args.command == "start"
    assert args.index == 7
    assert args.instructions == "Do not break tests"

    # Sessions
    args = parser.parse_args(["sessions"])
    assert args.command == "sessions"


@patch("scripts.jules_browser_bridge.subprocess.run")
def test_execute_chrome_js_success(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="hello%20world\n",
        stderr="",
    )
    code, stdout, stderr = execute_chrome_js("return 'hello world';")
    assert code == 0
    assert stdout == "hello world"
    assert stderr == ""


@patch("scripts.jules_browser_bridge.subprocess.run")
def test_execute_chrome_js_no_tab(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="NO_JULES_TAB\n",
        stderr="",
    )
    code, stdout, stderr = execute_chrome_js("return true;")
    assert stdout == "NO_JULES_TAB"


@patch("scripts.jules_browser_bridge.execute_chrome_js")
def test_check_jules_health(mock_exec):
    payload = {
        "status": "ok",
        "url": "https://jules.google.com/repo/github/IgorGanapolsky/trading/suggestions",
        "title": "Suggestions - Jules",
        "bodyLength": 5000,
        "hasSuggestions": True,
        "filterChips": ["All", "Performance"],
    }
    mock_exec.return_value = (0, json.dumps(payload), "")
    res = check_jules_health()
    assert res["status"] == "ok"
    assert res["hasSuggestions"] is True

    # Disconnected
    mock_exec.return_value = (0, "NO_JULES_TAB", "")
    res = check_jules_health()
    assert res["status"] == "disconnected"


@patch("scripts.jules_browser_bridge.execute_chrome_js")
def test_list_jules_suggestions(mock_exec):
    suggestions = [
        {
            "index": 0,
            "title": "Blocking time.sleep",
            "category": "performance",
            "location": "src/utils/market_data.py:556",
            "description": "Blocking sleep",
            "rationale": "Use async sleep",
        },
        {
            "index": 1,
            "title": "Timing Attack Vulnerability",
            "category": "security",
            "location": "src/agents/rag_webhook.py:1914",
            "description": "Timing attack",
            "rationale": "Use compare_digest",
        },
    ]
    mock_exec.return_value = (0, json.dumps(suggestions), "")

    # List all
    all_items = list_jules_suggestions("all")
    assert len(all_items) == 2

    # Filter security
    sec_items = list_jules_suggestions("security")
    assert len(sec_items) == 1
    assert sec_items[0]["category"] == "security"


@patch("scripts.jules_browser_bridge.execute_chrome_js")
def test_expand_suggestion(mock_exec):
    details = {
        "index": 24,
        "raw_summary": "Timing Attack Vulnerability",
        "location": "src/agents/rag_webhook.py:1914",
        "description": "Using string equality for token comparison",
        "rationale": "Use hmac.compare_digest",
        "full_detail_text": "Description Using string equality... Location src/agents/rag_webhook.py:1914",
    }
    mock_exec.side_effect = [
        (0, "CLICKED", ""),
        (0, json.dumps(details), ""),
    ]
    res = expand_suggestion(24)
    assert res is not None
    assert res["location"] == "src/agents/rag_webhook.py:1914"
    assert "compare_digest" in res["rationale"]


@patch("scripts.jules_browser_bridge.execute_chrome_js")
def test_dispatch_suggestion(mock_exec):
    mock_exec.side_effect = [
        (0, "LOADED", ""),
        (0, "APPENDED", ""),
        (0, "SUBMITTED", ""),
    ]
    res = dispatch_suggestion(10, custom_instructions="Focus on latency")
    assert res["status"] == "success"
    assert "successfully dispatched" in res["message"]


@patch("scripts.jules_browser_bridge.execute_chrome_js")
def test_list_recent_sessions(mock_exec):
    sessions = [
        {
            "id": "4995586535341526337",
            "url": "https://jules.google.com/session/4995586535341526337",
            "title": "is my repo ok?",
        }
    ]
    mock_exec.return_value = (0, json.dumps(sessions), "")
    res = list_recent_sessions()
    assert len(res) == 1
    assert res[0]["id"] == "4995586535341526337"


@patch("scripts.jules_browser_bridge.check_jules_health")
def test_main_cli(mock_health):
    mock_health.return_value = {"status": "ok"}
    assert main(["health"]) == 0
