"""Tests for scripts/workflow_health_monitor.py."""

from __future__ import annotations

from datetime import datetime, timedelta


def test_health_monitor_counts_failures_and_success_rate(tmp_path):
    import scripts.workflow_health_monitor as module

    monitor = module.WorkflowHealthMonitor(data_dir=str(tmp_path))
    now = datetime.now(tz=module.ET)

    monitor.get_expected_executions = lambda workflow_id, days=7: [now - timedelta(days=1), now]  # type: ignore[assignment]

    def _records(workflow_id, days=7):
        if workflow_id == "ci":
            return [
                {"timestamp": now - timedelta(hours=2), "status": "failure"},
                {"timestamp": now - timedelta(hours=1), "status": "success"},
            ]
        return [{"timestamp": now - timedelta(hours=1), "status": "success"}]

    monitor.get_execution_records = _records  # type: ignore[assignment]
    report = monitor.check_health(days=7)
    ci = report["workflows"]["ci"]

    assert ci["actual_executions"] == 2
    assert ci["success_executions"] == 1
    assert ci["failed_executions"] == 1
    assert ci["success_rate"] == 50.0
    assert ci["status"] in {"DEGRADED", "CRITICAL"}


def test_non_critical_critical_workflow_degrades_overall_health(tmp_path, monkeypatch):
    import scripts.workflow_health_monitor as module

    schedules = {
        "daily-trading": {
            "name": "Daily Trading Execution",
            "schedule": "weekdays",
            "time_et": "09:35",
            "critical": True,
        },
        "dashboard-update": {
            "name": "Dashboard Update",
            "schedule": "daily",
            "time_et": "10:00",
            "critical": False,
        },
    }
    monkeypatch.setattr(module, "WORKFLOW_SCHEDULES", schedules)

    monitor = module.WorkflowHealthMonitor(data_dir=str(tmp_path))
    now = datetime.now(tz=module.ET)
    monitor.get_expected_executions = lambda workflow_id, days=7: [now - timedelta(days=1)]  # type: ignore[assignment]

    def _records(workflow_id, days=7):
        if workflow_id == "daily-trading":
            return [{"timestamp": now - timedelta(hours=1), "status": "success"}]
        return []

    monitor.get_execution_records = _records  # type: ignore[assignment]
    report = monitor.check_health(days=7)

    assert report["workflows"]["dashboard-update"]["status"] == "CRITICAL"
    assert report["overall_health"] == "DEGRADED"
