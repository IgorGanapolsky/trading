#!/usr/bin/env python3
"""Guardrails for the autonomous dashboard workflow."""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    import yaml
except ImportError:
    pytest.skip("pyyaml not installed", allow_module_level=True)


WORKFLOW_PATH = Path(".github/workflows/update-progress-dashboard.yml")


def _load_workflow() -> dict:
    assert WORKFLOW_PATH.exists(), f"Workflow not found: {WORKFLOW_PATH}"
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    assert isinstance(workflow, dict)
    return workflow


def _triggers() -> dict:
    workflow = _load_workflow()
    triggers = workflow.get("on")
    if triggers is None:
        triggers = workflow.get(True, {})
    assert isinstance(triggers, dict)
    return triggers


def _steps() -> list[dict]:
    workflow = _load_workflow()
    jobs = workflow.get("jobs", {})
    update_dashboard = jobs.get("update-dashboard", {})
    steps = update_dashboard.get("steps", [])
    assert isinstance(steps, list)
    return steps


def test_workflow_is_scheduled_and_dispatchable() -> None:
    triggers = _triggers()
    assert "schedule" in triggers
    assert len(triggers["schedule"]) >= 2
    assert "workflow_dispatch" in triggers


def test_workflow_push_paths_cover_sqlite_analytics_runtime_surface() -> None:
    push_paths = _triggers().get("push", {}).get("paths", [])
    assert "scripts/build_sqlite_analytics.py" in push_paths
    assert "src/analytics/__init__.py" in push_paths
    assert "src/analytics/sqlite_analytics.py" in push_paths
    assert "src/core/trading_constants.py" in push_paths


def test_workflow_builds_and_uploads_sqlite_analytics_artifacts() -> None:
    steps = _steps()

    build_step = next(
        (step for step in steps if step.get("name") == "Build autonomous SQL analytics artifacts"),
        None,
    )
    assert build_step is not None
    build_script = build_step.get("run", "")
    assert "python3 scripts/build_sqlite_analytics.py" in build_script
    assert "artifacts/devloop/trading_analytics.sqlite" in build_script
    assert "artifacts/devloop/sql_analytics_summary.json" in build_script
    assert "artifacts/devloop/sql_analytics_summary.md" in build_script

    upload_step = next(
        (step for step in steps if step.get("name") == "Upload SQL analytics artifact"),
        None,
    )
    assert upload_step is not None
    assert upload_step.get("uses") == "actions/upload-artifact@v4"
    upload_path = upload_step.get("with", {}).get("path", "")
    assert "artifacts/devloop/trading_analytics.sqlite" in upload_path
    assert "artifacts/devloop/sql_analytics_summary.json" in upload_path
    assert "artifacts/devloop/sql_analytics_summary.md" in upload_path
