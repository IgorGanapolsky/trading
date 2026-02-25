"""Trading policy drift metrics for canonical-vs-doc consistency checks."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from src.core.trading_constants import (
    IRON_CONDOR_STOP_LOSS_MULTIPLIER,
    MAX_POSITIONS,
    NORTH_STAR_MONTHLY_AFTER_TAX,
)

DEFAULT_POLICY_DOC_PATHS: tuple[str, ...] = (
    ".claude/CLAUDE.md",
    ".claude/rules/risk-management.md",
    ".claude/rules/trading.md",
)

POLICY_KEYS: tuple[str, ...] = (
    "IRON_CONDOR_STOP_LOSS_MULTIPLIER",
    "NORTH_STAR_MONTHLY_AFTER_TAX",
    "MAX_POSITIONS",
)

_POLICY_VALUE_PATTERN = re.compile(
    r"(?P<key>IRON_CONDOR_STOP_LOSS_MULTIPLIER|NORTH_STAR_MONTHLY_AFTER_TAX|MAX_POSITIONS)"
    r"\s*[:=]\s*`?(?P<value>[0-9][0-9_,]*(?:\.[0-9]+)?)`?",
)


def canonical_policy_values() -> dict[str, float | int]:
    """Return canonical policy values from trading constants (A cohort)."""
    return {
        "IRON_CONDOR_STOP_LOSS_MULTIPLIER": float(IRON_CONDOR_STOP_LOSS_MULTIPLIER),
        "NORTH_STAR_MONTHLY_AFTER_TAX": float(NORTH_STAR_MONTHLY_AFTER_TAX),
        "MAX_POSITIONS": int(MAX_POSITIONS),
    }


def extract_policy_values_from_text(text: str) -> dict[str, float | int]:
    """Extract machine-readable policy values from documentation text."""
    values: dict[str, float | int] = {}
    for match in _POLICY_VALUE_PATTERN.finditer(text):
        key = match.group("key")
        raw_value = match.group("value").replace("_", "").replace(",", "")
        parsed = float(raw_value)
        if key == "MAX_POSITIONS":
            values[key] = int(round(parsed))
        else:
            values[key] = parsed
    return values


def _values_match(expected: float | int, actual: float | int) -> bool:
    if isinstance(expected, int):
        return int(actual) == expected
    return abs(float(actual) - expected) <= 1e-9


def collect_trading_policy_ab_metrics(
    repo_root: Path,
    policy_doc_paths: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Collect A/B metrics comparing canonical constants vs documented values.

    A cohort: canonical constants from ``src/core/trading_constants.py``.
    B cohort: declarations in policy docs.
    """
    root = repo_root.resolve()
    docs = list(policy_doc_paths or DEFAULT_POLICY_DOC_PATHS)
    canonical = canonical_policy_values()

    checks_total = 0
    checks_passed = 0
    drift_items: list[str] = []
    document_results: dict[str, dict[str, Any]] = {}

    for rel_path in docs:
        rel_posix = Path(rel_path).as_posix()
        abs_path = (root / rel_posix).resolve()
        result: dict[str, Any] = {
            "exists": abs_path.exists(),
            "values": {},
            "comparisons": {},
            "missing_keys": [],
        }

        if abs_path.exists():
            text = abs_path.read_text(encoding="utf-8", errors="replace")
            documented_values = extract_policy_values_from_text(text)
            result["values"] = documented_values
        else:
            documented_values = {}

        comparisons: dict[str, dict[str, Any]] = {}
        missing_keys: list[str] = []
        for key in POLICY_KEYS:
            checks_total += 1
            expected = canonical[key]
            actual = documented_values.get(key)

            if actual is None:
                missing_keys.append(key)
                comparisons[key] = {
                    "expected": expected,
                    "actual": None,
                    "matched": False,
                }
                reason = "missing file" if not abs_path.exists() else "missing declaration"
                drift_items.append(f"{rel_posix}: {reason} for {key}")
                continue

            matched = _values_match(expected, actual)
            comparisons[key] = {
                "expected": expected,
                "actual": actual,
                "matched": matched,
            }
            if matched:
                checks_passed += 1
            else:
                drift_items.append(f"{rel_posix}: {key} expected {expected} but found {actual}")

        result["comparisons"] = comparisons
        result["missing_keys"] = missing_keys
        document_results[rel_posix] = result

    checks_failed = checks_total - checks_passed
    return {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "cohort_a_canonical": canonical,
        "cohort_b_documents": document_results,
        "checks_total": checks_total,
        "checks_passed": checks_passed,
        "checks_failed": checks_failed,
        "match_rate": (checks_passed / checks_total) if checks_total else 1.0,
        "drift_detected": checks_failed > 0,
        "drift_items": drift_items,
    }


def write_trading_policy_ab_metrics(metrics: dict[str, Any], output_path: Path) -> None:
    """Persist policy A/B metrics as JSON."""
    target = output_path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
