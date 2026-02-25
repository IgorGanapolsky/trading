"""Delegation governance helpers for autonomous agent handoffs."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

RISK_TIERS: tuple[str, ...] = ("low", "medium", "high", "critical")
RISK_LEVEL = {tier: idx for idx, tier in enumerate(RISK_TIERS)}

HIGH_RISK_PATH_PREFIXES: tuple[str, ...] = (
    "src/orchestrator/",
    "src/risk/",
    "src/safety/",
    "scripts/autonomous_trader.py",
    "scripts/iron_condor_",
    "scripts/manage_iron_condor_positions.py",
    ".github/workflows/daily-trading.yml",
    ".github/workflows/iron-condor-",
)

CRITICAL_RISK_PATH_PREFIXES: tuple[str, ...] = (
    ".github/workflows/production-",
    "scripts/deploy_",
)

CAPABILITY_POLICY: dict[str, dict[str, Any]] = {
    "codex": {
        "max_risk_tier": "high",
        "allowed_scopes": {
            "read_repo",
            "write_repo",
            "run_tests",
            "update_ci",
            "collect_metrics",
            "open_pr",
        },
    },
    "autopilot": {
        "max_risk_tier": "medium",
        "allowed_scopes": {
            "read_repo",
            "write_repo",
            "run_tests",
            "collect_metrics",
        },
    },
    "guardian": {"max_risk_tier": "critical", "allowed_scopes": {"*"}},
    "human": {"max_risk_tier": "critical", "allowed_scopes": {"*"}},
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def infer_risk_tier(changed_paths: Sequence[str]) -> str:
    """Infer a conservative risk tier from changed paths."""
    if not changed_paths:
        return "low"

    has_medium = False
    has_high = False
    for raw_path in changed_paths:
        path = _normalize_path(raw_path)
        if not path:
            continue
        if any(path.startswith(prefix) for prefix in CRITICAL_RISK_PATH_PREFIXES):
            return "critical"
        if any(path.startswith(prefix) for prefix in HIGH_RISK_PATH_PREFIXES):
            has_high = True
            continue
        if path.startswith(("src/", "scripts/", ".github/workflows/")):
            has_medium = True

    if has_high:
        return "high"
    if has_medium:
        return "medium"
    return "low"


def required_acceptance_tests_for_tier(risk_tier: str) -> list[str]:
    """Return required verification checks for a given risk tier."""
    checks = ["lint", "format", "tests"]
    if risk_tier in {"medium", "high", "critical"}:
        checks.append("integration-smoke")
    if risk_tier in {"high", "critical"}:
        checks.append("workflow-contracts")
    if risk_tier == "critical":
        checks.append("full-regression")
    return checks


def required_step_names_for_tier(risk_tier: str) -> tuple[str, ...]:
    """Map risk tier to minimum gate step names that must pass."""
    base = [
        "AGENTS contract",
        "delegation contract",
        "trading policy drift",
        "lint",
        "format",
        "tests",
    ]
    if risk_tier in {"medium", "high", "critical"}:
        base.append("integration smoke")
    if risk_tier in {"high", "critical"}:
        base.append("workflow contracts")
    if risk_tier == "critical":
        base.append("full regression tests")
    return tuple(base)


def default_authority_scope_for_tier(risk_tier: str) -> list[str]:
    """Return least-privilege authority scopes for the requested risk tier."""
    scope = ["read_repo", "run_tests", "collect_metrics"]
    if risk_tier in {"medium", "high", "critical"}:
        scope.append("write_repo")
    if risk_tier in {"high", "critical"}:
        scope.append("update_ci")
    if risk_tier == "critical":
        scope.append("open_pr")
    return scope


def build_delegation_contract(
    *,
    changed_paths: Sequence[str],
    mode: str,
    assignee: str,
    fallback_assignee: str,
    risk_tier: str = "auto",
    objective: str | None = None,
    timeout_minutes: int = 35,
) -> dict[str, Any]:
    """Build a default delegation contract for the gate run."""
    resolved_risk_tier = infer_risk_tier(changed_paths) if risk_tier == "auto" else risk_tier
    return {
        "contract_version": 1,
        "created_at_utc": _utc_now(),
        "objective": objective
        or f"Validate and handoff autonomous changes ({len(changed_paths)} paths).",
        "assignee": assignee,
        "fallback_assignee": fallback_assignee,
        "risk_tier": resolved_risk_tier,
        "authority_scope": default_authority_scope_for_tier(resolved_risk_tier),
        "acceptance_tests": required_acceptance_tests_for_tier(resolved_risk_tier),
        "timeout_minutes": timeout_minutes,
        "rollback_on_failure": True,
        "mode_requested": mode,
        "changed_path_count": len(changed_paths),
    }


def _validate_assignee_capability(
    *,
    assignee: str,
    risk_tier: str,
    authority_scope: Sequence[str],
    issues: list[str],
) -> None:
    profile = CAPABILITY_POLICY.get(assignee)
    if profile is None:
        issues.append(f"assignee '{assignee}' missing in capability policy")
        return

    max_risk_tier = str(profile.get("max_risk_tier", "low"))
    if max_risk_tier not in RISK_LEVEL:
        issues.append(f"assignee '{assignee}' has invalid max risk tier '{max_risk_tier}'")
        return

    if RISK_LEVEL[risk_tier] > RISK_LEVEL[max_risk_tier]:
        issues.append(
            f"assignee '{assignee}' cannot run risk tier '{risk_tier}' (max '{max_risk_tier}')"
        )

    allowed = profile.get("allowed_scopes", set())
    if "*" in allowed:
        return
    for scope in authority_scope:
        if scope not in allowed:
            issues.append(f"assignee '{assignee}' not allowed scope '{scope}'")


def validate_delegation_contract(
    contract: Mapping[str, Any], changed_paths: Sequence[str] | None = None
) -> list[str]:
    """Validate contract structure, risk tier, and capability routing."""
    issues: list[str] = []
    required_keys = {
        "contract_version",
        "created_at_utc",
        "objective",
        "assignee",
        "fallback_assignee",
        "risk_tier",
        "authority_scope",
        "acceptance_tests",
        "timeout_minutes",
        "rollback_on_failure",
    }
    for key in sorted(required_keys):
        if key not in contract:
            issues.append(f"missing required field '{key}'")

    risk_tier = str(contract.get("risk_tier") or "")
    if risk_tier not in RISK_LEVEL:
        issues.append(f"invalid risk_tier '{risk_tier}'")
        return issues

    timeout_minutes = contract.get("timeout_minutes")
    if not isinstance(timeout_minutes, int) or timeout_minutes <= 0:
        issues.append("timeout_minutes must be a positive integer")

    authority_scope = contract.get("authority_scope")
    if not isinstance(authority_scope, list) or not all(
        isinstance(scope, str) and scope for scope in authority_scope
    ):
        issues.append("authority_scope must be a non-empty list of strings")
        authority_scope = []

    acceptance_tests = contract.get("acceptance_tests")
    if not isinstance(acceptance_tests, list) or not all(
        isinstance(test_name, str) and test_name for test_name in acceptance_tests
    ):
        issues.append("acceptance_tests must be a non-empty list of strings")
        acceptance_tests = []

    required_tests = required_acceptance_tests_for_tier(risk_tier)
    missing_tests = [check for check in required_tests if check not in acceptance_tests]
    if missing_tests:
        issues.append(f"acceptance_tests missing required checks: {', '.join(missing_tests)}")

    assignee = str(contract.get("assignee") or "")
    fallback_assignee = str(contract.get("fallback_assignee") or "")
    if not assignee:
        issues.append("assignee must be a non-empty string")
    else:
        _validate_assignee_capability(
            assignee=assignee, risk_tier=risk_tier, authority_scope=authority_scope, issues=issues
        )

    if not fallback_assignee:
        issues.append("fallback_assignee must be a non-empty string")
    elif fallback_assignee not in CAPABILITY_POLICY:
        issues.append(f"fallback_assignee '{fallback_assignee}' missing in capability policy")

    if changed_paths is not None:
        inferred = infer_risk_tier(changed_paths)
        if RISK_LEVEL[risk_tier] < RISK_LEVEL[inferred]:
            issues.append(
                f"risk_tier '{risk_tier}' is lower than inferred tier '{inferred}' for changed paths"
            )

    return issues


def build_fallback_plan(
    *,
    contract: Mapping[str, Any],
    failed_steps: Sequence[str],
    report_json_path: Path,
) -> dict[str, Any]:
    """Build a deterministic fallback handoff plan when gate checks fail."""
    return {
        "generated_at_utc": _utc_now(),
        "status": "fallback_required",
        "fallback_assignee": contract.get("fallback_assignee"),
        "original_assignee": contract.get("assignee"),
        "risk_tier": contract.get("risk_tier"),
        "failed_steps": list(failed_steps),
        "report_json": report_json_path.as_posix(),
        "actions": [
            "Review failing step output in gate report",
            "Patch only files implicated by failed checks",
            "Re-run gate with same delegation contract",
        ],
    }


def append_handoff_audit_record(log_path: Path, record: Mapping[str, Any]) -> dict[str, Any]:
    """Append a tamper-evident audit entry to a JSONL log using hash chaining."""
    previous_hash = "GENESIS"
    if log_path.exists():
        for line in reversed(log_path.read_text(encoding="utf-8").splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and isinstance(parsed.get("hash"), str):
                previous_hash = parsed["hash"]
                break

    payload = dict(record)
    payload["previous_hash"] = previous_hash
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    payload["hash"] = payload_hash

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
    return payload
