"""Fail-fast tabular helpers inspired by Polars 2.0 defaults.

Steal from https://pola.rs/posts/announcing-polars-2/ (mechanics only):

* streaming/lazy-style schema collect before materializing expensive work
* strict height checks (no silent horizontal pad with null)
* refuse silent lossy ID/count coercion through float64

No Polars dependency — pure Python for the trading ledger path.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence


class ShapeError(ValueError):
    """Row-count / shape mismatch (Polars 2 strict concat class)."""


class LosslessCoercionError(ValueError):
    """Lossy type coercion refused (Polars 2 is_in / float-id class)."""


class SchemaError(ValueError):
    """Schema-level mismatch caught before materializing metrics."""


def assert_equal_heights(
    *tables: Sequence[Any],
    labels: Sequence[str] | None = None,
    context: str = "strict_horizontal",
) -> int:
    """Require equal lengths; raise ShapeError instead of padding with null."""
    if not tables:
        return 0
    heights = [len(table) for table in tables]
    if len(set(heights)) == 1:
        return heights[0]
    names = list(labels) if labels is not None else [f"col_{i}" for i in range(len(tables))]
    detail = ", ".join(f"{name}={height}" for name, height in zip(names, heights, strict=True))
    raise ShapeError(
        f"cannot concat/zip with different heights in strict mode ({context}): {detail}; "
        "opt in to padding only with an explicit horizontal_extend path"
    )


def strict_horizontal_zip(
    columns: Mapping[str, Sequence[Any]],
    *,
    context: str = "strict_horizontal",
) -> list[dict[str, Any]]:
    """Zip named columns into row dicts only when all heights match."""
    keys = list(columns.keys())
    values = [columns[key] for key in keys]
    height = assert_equal_heights(*values, labels=keys, context=context)
    return [{key: values[i][row] for i, key in enumerate(keys)} for row in range(height)]


def _is_ascii_decimal(text: str) -> bool:
    """True only for optional leading '-' plus ASCII digits 0-9."""
    if not text:
        return False
    body = text[1:] if text.startswith("-") else text
    return bool(body) and all("0" <= ch <= "9" for ch in body)


def parse_strict_int(value: Any, *, field: str, allow_negative: bool = False) -> int:
    """Parse a whole-number count/ID without float64 round-trip."""
    if isinstance(value, bool):
        raise LosslessCoercionError(f"{field}: bool is not a count/id")
    if isinstance(value, int):
        if value < 0 and not allow_negative:
            raise LosslessCoercionError(f"{field}: refuse negative count {value}")
        return value
    if isinstance(value, float):
        if not value.is_integer():
            raise LosslessCoercionError(
                f"{field}: refuse lossy float→int coercion for non-integer {value!r}"
            )
        # Still refuse large floats that cannot be represented exactly in float64 mantissa.
        as_int = int(value)
        if abs(as_int) > (2**53) or float(as_int) != value:
            raise LosslessCoercionError(
                f"{field}: refuse float id/count {value!r} outside exact float64 integer range"
            )
        raise LosslessCoercionError(
            f"{field}: refuse float→int coercion for count/id {value!r}; pass an int or digit string"
        )
    if isinstance(value, str):
        text = value.strip()
        if not text or text.lower() in {"none", "null", "nan"}:
            raise LosslessCoercionError(f"{field}: empty/null string is not a count/id")
        if not _is_ascii_decimal(text):
            raise LosslessCoercionError(f"{field}: refuse non-digit string count/id {value!r}")
        try:
            parsed = int(text)
        except ValueError as exc:  # pragma: no cover - ASCII guard should prevent this
            raise LosslessCoercionError(
                f"{field}: refuse non-digit string count/id {value!r}"
            ) from exc
        if parsed < 0 and not allow_negative:
            raise LosslessCoercionError(f"{field}: refuse negative count {parsed}")
        return parsed
    if value is None:
        raise LosslessCoercionError(f"{field}: None is not a count/id")
    raise LosslessCoercionError(f"{field}: unsupported count/id type {type(value).__name__}")


def parse_optional_strict_int(
    value: Any, *, field: str, allow_negative: bool = False
) -> int | None:
    """Like parse_strict_int but maps missing/empty to None."""
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return parse_strict_int(value, field=field, allow_negative=allow_negative)


def assert_identity_value(value: Any, *, field: str = "id") -> str:
    """Accept string/int identity values; refuse floats."""
    if isinstance(value, float):
        raise LosslessCoercionError(
            f"{field}: refuse float identity {value!r}; use a string or int id"
        )
    if isinstance(value, bool) or value is None:
        raise LosslessCoercionError(f"{field}: invalid identity type {type(value).__name__}")
    text = str(value).strip()
    if not text:
        raise LosslessCoercionError(f"{field}: empty id")
    return text


def assert_id_equality(left: Any, right: Any, *, field: str = "id") -> str:
    """Compare identifiers as strings; never via float equality."""
    if isinstance(left, float) or isinstance(right, float):
        raise LosslessCoercionError(
            f"{field}: refuse float identity comparison "
            f"({left!r} vs {right!r}); cast explicitly if intentional"
        )
    left_s = str(left).strip()
    right_s = str(right).strip()
    if not left_s or not right_s:
        raise LosslessCoercionError(f"{field}: empty id")
    if left_s != right_s:
        raise LosslessCoercionError(f"{field}: mismatch {left_s!r} != {right_s!r}")
    return left_s


def collect_row_schema(
    rows: Iterable[Mapping[str, Any]],
    *,
    required: Sequence[str],
    numeric_fields: Sequence[str] = (),
    identity_fields: Sequence[str] = (),
    max_rows: int | None = None,
) -> dict[str, Any]:
    """Resolve schema/types without computing metrics (collect_schema analog).

    Returns a compact report. Raises SchemaError when required fields are absent
    on any inspected row or numeric fields are non-numeric.
    """
    required_set = list(required)
    numeric_set = list(numeric_fields)
    identity_set = list(identity_fields)
    inspected = 0
    missing: dict[str, int] = {name: 0 for name in required_set}
    bad_numeric: dict[str, int] = {name: 0 for name in numeric_set}
    bad_identity: dict[str, int] = {name: 0 for name in identity_set}
    field_types: dict[str, set[str]] = {}

    for row in rows:
        if not isinstance(row, Mapping):
            raise SchemaError(f"row {inspected}: expected mapping, got {type(row).__name__}")
        inspected += 1
        for key, value in row.items():
            field_types.setdefault(str(key), set()).add(type(value).__name__)
        for name in required_set:
            if name not in row or row.get(name) in (None, ""):
                missing[name] += 1
        for name in numeric_set:
            if name not in row or row.get(name) in (None, ""):
                continue
            value = row.get(name)
            if isinstance(value, bool) or not isinstance(value, (int, float, str)):
                bad_numeric[name] += 1
                continue
            if isinstance(value, str):
                try:
                    float(value)
                except ValueError:
                    bad_numeric[name] += 1
        for name in identity_set:
            if name not in row or row.get(name) in (None, ""):
                continue
            try:
                assert_identity_value(row.get(name), field=name)
            except LosslessCoercionError:
                bad_identity[name] += 1
        if max_rows is not None and inspected >= max_rows:
            break

    issues: list[str] = []
    for name, count in missing.items():
        if count:
            issues.append(f"missing_required:{name}:{count}/{inspected}")
    for name, count in bad_numeric.items():
        if count:
            issues.append(f"non_numeric:{name}:{count}/{inspected}")
    for name, count in bad_identity.items():
        if count:
            issues.append(f"lossy_identity:{name}:{count}/{inspected}")

    report = {
        "inspected_rows": inspected,
        "required": required_set,
        "numeric_fields": numeric_set,
        "identity_fields": identity_set,
        "field_types": {key: sorted(values) for key, values in sorted(field_types.items())},
        "missing_required_counts": {k: v for k, v in missing.items() if v},
        "non_numeric_counts": {k: v for k, v in bad_numeric.items() if v},
        "lossy_identity_counts": {k: v for k, v in bad_identity.items() if v},
        "issues": issues,
        "ok": not issues,
    }
    if issues:
        raise SchemaError("; ".join(issues))
    return report
