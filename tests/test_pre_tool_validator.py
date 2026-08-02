"""Unit tests for PreToolValidator."""

from __future__ import annotations

from src.validators.pre_tool_validator import PreToolValidator


def test_valid_execute_trade() -> None:
    res = PreToolValidator.validate_tool_call(
        "execute_trade", {"symbol": "spy", "action": "buy", "quantity": 10}
    )
    assert res.is_valid is True
    assert res.normalized_input["symbol"] == "SPY"
    assert len(res.errors) == 0


def test_missing_required_param() -> None:
    res = PreToolValidator.validate_tool_call("execute_trade", {"symbol": "SPY", "quantity": 10})
    assert res.is_valid is False
    assert any("Missing required parameter 'action'" in err for err in res.errors)


def test_invalid_type_param() -> None:
    res = PreToolValidator.validate_tool_call(
        "execute_trade", {"symbol": "SPY", "action": "buy", "quantity": "ten"}
    )
    assert res.is_valid is False
    assert any("must be of type" in err for err in res.errors)


def test_disallowed_enum_value() -> None:
    res = PreToolValidator.validate_tool_call(
        "execute_trade", {"symbol": "SPY", "action": "invalid_action", "quantity": 10}
    )
    assert res.is_valid is False
    assert any("not in allowed set" in err for err in res.errors)


def test_unregistered_tool_passes() -> None:
    res = PreToolValidator.validate_tool_call("custom_unregistered_tool", {"foo": "bar"})
    assert res.is_valid is True
