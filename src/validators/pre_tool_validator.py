"""
Structured Pre-Tool Validator Gate.

Validates all incoming tool arguments, required parameters, and types BEFORE
tool execution. Rejects malformed arguments early to save token overhead and
prevent downstream runtime exceptions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
    def validate_tool_call(cls, tool_name: str, tool_input: dict[str, Any]) -> ValidationResult:
        """Validates tool call input against registered parameter schemas."""
        errors: list[str] = []
        if not isinstance(tool_input, dict):
            return ValidationResult(is_valid=False, errors=["tool_input must be a dictionary"])

        schema = cls.REQUIRED_SCHEMAS.get(tool_name)
        if not schema:
            # Unregistered tools pass validation by default
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
