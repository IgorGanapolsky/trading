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


@patch("scripts.jules_browser_bridge.subprocess.run")
def test_execute_chrome_js_null_and_error(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="__NULL__\n",
        stderr="",
    )
    code, stdout, stderr = execute_chrome_js("return null;")
    assert code == 0
    assert stdout == ""

    # Non-zero returncode
    mock_run.return_value = MagicMock(
        returncode=1,
        stdout="syntax error",
        stderr="err",
    )
    code, stdout, stderr = execute_chrome_js("return syntax;")
    assert code == 1
    assert stderr == "err"


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

    # AppleScript execution error
    mock_exec.return_value = (1, "fail", "OSAScript error")
    res = check_jules_health()
    assert res["status"] == "error"

    # JS __error__ returned
    mock_exec.return_value = (0, json.dumps({"__error__": "ReferenceError"}), "")
    res = check_jules_health()
    assert res["status"] == "error"
    assert "ReferenceError" in res["message"]

    # Invalid JSON
    mock_exec.return_value = (0, "invalid-json{{{", "")
    res = check_jules_health()
    assert res["status"] == "error"


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
        {
            "index": 2,
            "title": "Missing test file",
            "category": "testing",
            "location": "src/signals/test.py",
            "description": "Test gap",
            "rationale": "Add tests",
        },
        {
            "index": 3,
            "title": "Too many parameters",
            "category": "code_health",
            "location": "src/signals/param.py",
            "description": "Code smell",
            "rationale": "Refactor params",
        },
    ]
    mock_exec.return_value = (0, json.dumps(suggestions), "")

    # List all
    all_items = list_jules_suggestions("all")
    assert len(all_items) == 4

    # Filter security
    sec_items = list_jules_suggestions("security")
    assert len(sec_items) == 1
    assert sec_items[0]["category"] == "security"

    # Filter testing
    test_items = list_jules_suggestions("testing")
    assert len(test_items) == 1

    # Filter code_health
    ch_items = list_jules_suggestions("code_health")
    assert len(ch_items) == 1

    # Error handling
    mock_exec.return_value = (0, "NO_JULES_TAB", "")
    assert list_jules_suggestions() == []

    mock_exec.return_value = (0, "not-json", "")
    assert list_jules_suggestions() == []


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

    # Click failed
    mock_exec.side_effect = [(0, "FAILED", "")]
    assert expand_suggestion(99) is None

    # Invalid JSON on details
    mock_exec.side_effect = [(0, "CLICKED", ""), (0, "bad-json", "")]
    assert expand_suggestion(24) is None


@patch("scripts.jules_browser_bridge.execute_chrome_js")
def test_dispatch_suggestion_success(mock_exec):
    mock_exec.side_effect = [
        (0, "LOADED", ""),
        (0, "APPENDED", ""),
        (0, "SUBMITTED", ""),
    ]
    res = dispatch_suggestion(10, custom_instructions="Focus on latency")
    assert res["status"] == "success"
    assert "successfully dispatched" in res["message"]


@patch("scripts.jules_browser_bridge.execute_chrome_js")
def test_dispatch_suggestion_load_failure(mock_exec):
    mock_exec.return_value = (0, "LOAD_FAILED", "")
    res = dispatch_suggestion(10)
    assert res["status"] == "error"
    assert "Failed to load" in res["message"]


@patch("scripts.jules_browser_bridge.execute_chrome_js")
def test_dispatch_suggestion_append_failure_prevents_submit(mock_exec):
    # Regression test: append error must abort and prevent submit_js from running
    mock_exec.side_effect = [
        (0, "LOADED", ""),
        (0, "APPEND_FAILED", "Composer not found"),
    ]
    res = dispatch_suggestion(10)
    assert res["status"] == "error"
    assert "Failed to append safety constraints" in res["message"]
    # Verify execute_chrome_js was called exactly twice (load, append) and NOT a third time (submit)
    assert mock_exec.call_count == 2


@patch("scripts.jules_browser_bridge.execute_chrome_js")
def test_dispatch_suggestion_submit_failure(mock_exec):
    mock_exec.side_effect = [
        (0, "LOADED", ""),
        (0, "APPENDED", ""),
        (0, "BUTTON_NOT_FOUND", ""),
    ]
    res = dispatch_suggestion(10)
    assert res["status"] == "error"
    assert "Failed to submit" in res["message"]


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

    # Tab missing or error
    mock_exec.return_value = (0, "NO_JULES_TAB", "")
    assert list_recent_sessions() == []

    mock_exec.return_value = (0, "corrupt", "")
    assert list_recent_sessions() == []


@patch("scripts.jules_browser_bridge.check_jules_health")
def test_main_cli_health(mock_health):
    mock_health.return_value = {"status": "ok"}
    assert main(["health"]) == 0

    mock_health.return_value = {"status": "error"}
    assert main(["health"]) == 1


@patch("scripts.jules_browser_bridge.list_jules_suggestions")
def test_main_cli_list(mock_list, capsys):
    mock_list.return_value = [
        {
            "index": 0,
            "category": "performance",
            "title": "Cache VIX",
            "location": "src/vix.py:12",
        }
    ]
    assert main(["list"]) == 0
    captured = capsys.readouterr()
    assert "Found 1 suggestions" in captured.out
    assert "Cache VIX" in captured.out

    assert main(["list", "--json"]) == 0
    captured = capsys.readouterr()
    assert '"Cache VIX"' in captured.out


@patch("scripts.jules_browser_bridge.expand_suggestion")
def test_main_cli_show(mock_expand, capsys):
    mock_expand.return_value = {
        "index": 1,
        "location": "src/a.py",
        "description": "desc",
        "rationale": "rat",
        "full_detail_text": "full text",
    }
    assert main(["show", "1"]) == 0
    captured = capsys.readouterr()
    assert "=== Suggestion [1] Details ===" in captured.out

    assert main(["show", "1", "--json"]) == 0
    captured = capsys.readouterr()
    assert '"location": "src/a.py"' in captured.out

    # Not found
    mock_expand.return_value = None
    assert main(["show", "99"]) == 1


@patch("scripts.jules_browser_bridge.dispatch_suggestion")
def test_main_cli_start(mock_dispatch):
    mock_dispatch.return_value = {"status": "success", "message": "Dispatched"}
    assert main(["start", "1"]) == 0

    mock_dispatch.return_value = {"status": "error", "message": "Failed"}
    assert main(["start", "1"]) == 1


@patch("scripts.jules_browser_bridge.list_recent_sessions")
def test_main_cli_sessions(mock_sessions, capsys):
    mock_sessions.return_value = [{"id": "123", "title": "Test session"}]
    assert main(["sessions"]) == 0
    captured = capsys.readouterr()
    assert "Test session" in captured.out
