from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "build_sqlite_analytics.py"
EXTERNAL_CWD = PROJECT_ROOT.parent


def test_build_sqlite_analytics_help_runs_without_pythonpath() -> None:
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--help"],
        cwd=str(EXTERNAL_CWD),
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Build SQLite analytics artifacts" in result.stdout
