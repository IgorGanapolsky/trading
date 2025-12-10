import json
from datetime import datetime

import scripts.generate_progress_dashboard as g


def test_format_recent_runs_empty():
    assert "—" in g.format_recent_runs([])


def test_format_recent_runs_formats_link():
    runs = [
        {
            "ts": datetime.utcnow().isoformat() + "Z",
            "status": "failure",
            "failing_step": "Install dependencies",
            "error": "pip timeout",
            "run_number": "123",
            "actions_url": "https://example.com/run/123",
        }
    ]
    out = g.format_recent_runs(runs)
    assert "FAILURE" in out
    assert "[#123](https://example.com/run/123)" in out
    assert "Install dependencies" in out


def test_load_run_log_reads_and_orders(tmp_path, monkeypatch):
    log = tmp_path / "trading_runs.jsonl"
    entries = [
        {"ts": "2025-12-03T00:00:00Z", "status": "success"},
        {"ts": "2025-12-04T00:00:00Z", "status": "failure"},
    ]
    log.write_text("\n".join(json.dumps(e) for e in entries))
    monkeypatch.setattr(g, "RUN_LOG", log)
    runs = g.load_run_log(max_items=5)
    assert len(runs) == 2
    # newest first
    assert runs[0]["status"] == "failure"
