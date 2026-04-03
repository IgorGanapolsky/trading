from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNNER_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "ci" / "run_all_tests.sh"


def _seed_runner_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "tests" / "integration").mkdir(parents=True)
    (repo / "src").mkdir(parents=True)
    (repo / "scripts" / "ci").mkdir(parents=True)
    shutil.copy2(RUNNER_SCRIPT_PATH, repo / "scripts" / "ci" / "run_all_tests.sh")

    (repo / "scripts" / "ci" / "check_critical_coverage.py").write_text(
        "import sys\nprint('critical coverage ok')\nsys.exit(0)\n",
        encoding="utf-8",
    )
    (repo / "src" / "sample.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n",
        encoding="utf-8",
    )
    (repo / "tests" / "test_core.py").write_text(
        textwrap.dedent(
            """
            from src.sample import add

            def test_add():
                assert add(2, 3) == 5
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return repo


def _runner_env(report_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    for key in (
        "CORE_TARGETS",
        "INTEGRATION_TARGETS",
        "REPORT_DIR",
        "PYTHON_BIN",
        "COV_TARGET",
        "COV_FAIL_UNDER",
        "CRITICAL_COVERAGE_SCRIPT",
    ):
        env.pop(key, None)
    env.update(
        {
            "PYTHON_BIN": sys.executable,
            "REPORT_DIR": str(report_dir),
            "HEARTBEAT_SECONDS": "1",
            "CORE_TIMEOUT_MINUTES": "1",
            "INTEGRATION_TIMEOUT_MINUTES": "1",
            "COV_FAIL_UNDER": "0",
        }
    )
    return env


def test_runner_generates_reports_for_core_and_integration(tmp_path: Path):
    repo = _seed_runner_repo(tmp_path)
    (repo / "tests" / "integration" / "test_integration.py").write_text(
        textwrap.dedent(
            """
            from src.sample import add

            def test_integration_add():
                assert add(10, 5) == 15
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    report_dir = repo / "artifacts" / "reports"

    result = subprocess.run(
        ["bash", "scripts/ci/run_all_tests.sh"],
        cwd=repo,
        env=_runner_env(report_dir),
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (repo / "coverage.xml").exists()
    assert (report_dir / "junit-core.xml").exists()
    assert (report_dir / "junit-integration.xml").exists()
    assert (report_dir / "coverage.txt").exists()
    assert "phase=core passed" in result.stdout
    assert "phase=integration passed" in result.stdout


def test_runner_skips_integration_after_core_failure(tmp_path: Path):
    repo = _seed_runner_repo(tmp_path)
    (repo / "tests" / "test_core.py").write_text(
        "def test_fail():\n    assert False\n",
        encoding="utf-8",
    )
    (repo / "tests" / "integration" / "test_integration.py").write_text(
        "def test_should_not_run():\n    assert True\n",
        encoding="utf-8",
    )
    report_dir = repo / "artifacts" / "reports"

    result = subprocess.run(
        ["bash", "scripts/ci/run_all_tests.sh"],
        cwd=repo,
        env=_runner_env(report_dir),
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode != 0
    assert "phase=core failed" in result.stdout
    assert not (report_dir / "junit-integration.xml").exists()


def test_runner_reports_missing_integration_tests_truthfully(tmp_path: Path):
    repo = _seed_runner_repo(tmp_path)
    report_dir = repo / "artifacts" / "reports"

    result = subprocess.run(
        ["bash", "scripts/ci/run_all_tests.sh"],
        cwd=repo,
        env=_runner_env(report_dir),
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "integration phase skipped: no tests/integration test files" in result.stdout
    assert not (report_dir / "junit-integration.xml").exists()


def test_runner_supports_multiple_coverage_targets(tmp_path: Path):
    repo = _seed_runner_repo(tmp_path)
    (repo / "scripts" / "sample_script.py").write_text(
        "def ping() -> str:\n    return 'pong'\n",
        encoding="utf-8",
    )
    (repo / "tests" / "test_script.py").write_text(
        textwrap.dedent(
            """
            from scripts.sample_script import ping

            def test_ping():
                assert ping() == "pong"
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    report_dir = repo / "artifacts" / "reports"
    env = _runner_env(report_dir)
    env["COV_TARGET"] = "src scripts"

    result = subprocess.run(
        ["bash", "scripts/ci/run_all_tests.sh"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    coverage_xml = (repo / "coverage.xml").read_text(encoding="utf-8")
    assert "sample_script.py" in coverage_xml
