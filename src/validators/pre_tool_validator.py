"""
Structured Pre-Tool Validator Gate.

Validates all incoming tool arguments, required parameters, and types BEFORE
tool execution. Rejects malformed arguments early to save token overhead and
prevent downstream runtime exceptions.

Production rule: money-moving tool names FAIL CLOSED when unregistered.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Unregistered tools that can move money / alter risk → reject (fail-closed).
FAIL_CLOSED_TOOL_PREFIXES: tuple[str, ...] = (
    "execute_",
    "place_",
    "submit_",
    "close_",
    "liquidat",
    "cancel_order",
    "transfer_",
    "withdraw",
)

FAIL_CLOSED_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "execute_trade",
        "place_order",
        "submit_order",
        "close_position",
        "close_all_positions",
        "liquidat_positions",
        "cancel_order",
        "cancel_all_orders",
    }
)


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    normalized_input: dict[str, Any] = field(default_factory=dict)


class PreToolValidator:
    """Pre-execution schema and argument validator for agent tool invocations."""

    REQUIRED_SCHEMAS: dict[str, dict[str, Any]] = {
        "execute_trade": {
            "required": ["symbol", "action", "quantity"],
            "types": {"symbol": str, "action": str, "quantity": (int, float)},
            "allowed_values": {"action": ["buy", "sell", "sell_short", "buy_to_cover"]},
        },
        "place_order": {
            "required": ["symbol", "side", "qty", "type"],
            "types": {"symbol": str, "side": str, "qty": (int, float), "type": str},
            "allowed_values": {
                "side": ["buy", "sell"],
                "type": ["market", "limit", "stop", "stop_limit"],
            },
        },
        "query_rag": {
            "required": ["query"],
            "types": {"query": str},
        },
    }

    @classmethod
    def _is_money_tool(cls, tool_name: str) -> bool:
        name = (tool_name or "").strip().lower()
        if name in FAIL_CLOSED_TOOL_NAMES:
            return True
        return any(name.startswith(p) or p in name for p in FAIL_CLOSED_TOOL_PREFIXES)

    @classmethod
    def validate_tool_call(cls, tool_name: str, tool_input: dict[str, Any]) -> ValidationResult:
        """Validates tool call input against registered parameter schemas."""
        errors: list[str] = []
        if not isinstance(tool_input, dict):
            return ValidationResult(is_valid=False, errors=["tool_input must be a dictionary"])

        schema = cls.REQUIRED_SCHEMAS.get(tool_name)
        if not schema:
            # Fail-closed for money tools; advisory tools may pass unregistered.
            if cls._is_money_tool(tool_name):
                return ValidationResult(
                    is_valid=False,
                    errors=[
                        f"FAIL_CLOSED: unregistered money-moving tool '{tool_name}' "
                        "requires an explicit schema before execution"
                    ],
                    normalized_input={},
                )
            return ValidationResult(is_valid=True, errors=[], normalized_input=tool_input)

        # Check required fields
        for field_name in schema.get("required", []):
            if field_name not in tool_input or tool_input[field_name] is None:
                errors.append(f"Missing required parameter '{field_name}' for tool '{tool_name}'")

        # Check types and allowed values
        for field_name, expected_type in schema.get("types", {}).items():
            if field_name in tool_input and tool_input[field_name] is not None:
                val = tool_input[field_name]
                if not isinstance(val, expected_type):
                    errors.append(
                        f"Parameter '{field_name}' must be of type {expected_type}, got {type(val)}"
                    )

        for field_name, allowed in schema.get("allowed_values", {}).items():
            if field_name in tool_input and tool_input[field_name] is not None:
                val = tool_input[field_name]
                if str(val).lower() not in [str(a).lower() for a in allowed]:
                    errors.append(
                        f"Parameter '{field_name}' value '{val}' not in allowed set: {allowed}"
                    )

        normalized = dict(tool_input)
        if "symbol" in normalized and isinstance(normalized["symbol"], str):
            normalized["symbol"] = normalized["symbol"].upper().strip()

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            normalized_input=normalized if len(errors) == 0 else tool_input,
        )
