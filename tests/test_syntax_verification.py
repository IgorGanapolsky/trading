"""
Comprehensive syntax verification tests.

Created after three critical syntax failures:
- Dec 11: alpaca_executor.py syntax error (ll_009)
- Dec 13: autonomous_trader.py f-string error (ll_024)
- Dec 10-11: CI failures blocked trading (ci_failure_blocked_trading)

This test suite prevents syntax errors from reaching production.
"""

import ast
import subprocess
import sys
from pathlib import Path
from typing import List

import pytest


class TestSyntaxVerification:
    """Verify Python syntax across critical files."""

    @pytest.fixture
    def project_root(self) -> Path:
        """Get project root directory."""
        return Path(__file__).parent.parent

    @pytest.fixture
    def critical_files(self, project_root: Path) -> List[Path]:
        """Critical files that must always be syntactically valid."""
        return [
            project_root / "src" / "orchestrator" / "main.py",
            project_root / "src" / "execution" / "alpaca_executor.py",
            project_root / "src" / "risk" / "trade_gateway.py",
            project_root / "scripts" / "autonomous_trader.py",
            project_root / "scripts" / "pre_merge_gate.py",
        ]

    def test_ll_009_no_syntax_errors_in_critical_files(
        self, critical_files: List[Path]
    ):
        """Prevent ll_009: Syntax errors in critical trading files.

        Dec 11, 2025: Syntax error in alpaca_executor.py broke all trading.
        This test ensures all critical files have valid Python syntax.
        """
        errors = []
        for file_path in critical_files:
            if not file_path.exists():
                errors.append(f"Missing file: {file_path}")
                continue

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    code = f.read()
                ast.parse(code)
            except SyntaxError as e:
                errors.append(f"{file_path}: Line {e.lineno}: {e.msg}")

        assert not errors, f"REGRESSION ll_009: Syntax errors found:\n" + "\n".join(
            errors
        )

    def test_ll_024_no_fstring_backslash_escapes(self, project_root: Path):
        """Prevent ll_024: F-string backslash escapes (Python 3.12+ incompatible).

        Dec 13, 2025: F-string with backslash in autonomous_trader.py crashed script.
        Python 3.12+ forbids backslashes in f-string expressions.
        """
        scripts_dir = project_root / "scripts"
        src_dir = project_root / "src"

        dangerous_patterns = []

        for directory in [scripts_dir, src_dir]:
            for py_file in directory.rglob("*.py"):
                try:
                    with open(py_file, "r", encoding="utf-8") as f:
                        content = f.read()

                    # Simplified check: Look for f-strings with escaped quotes inside expressions
                    # Pattern: f"...{...\"...}..."
                    lines = content.split("\n")
                    for line_num, line in enumerate(lines, 1):
                        if "f\"" in line or "f'" in line:
                            # Check if there's a backslash inside curly braces
                            in_fstring = False
                            brace_depth = 0
                            for i, char in enumerate(line):
                                if char == "f" and i + 1 < len(line) and line[i + 1] in [
                                    '"',
                                    "'",
                                ]:
                                    in_fstring = True
                                if in_fstring and char == "{":
                                    brace_depth += 1
                                elif in_fstring and char == "}":
                                    brace_depth -= 1
                                elif (
                                    in_fstring
                                    and brace_depth > 0
                                    and char == "\\"
                                    and i + 1 < len(line)
                                ):
                                    if line[i + 1] in ['"', "'"]:
                                        dangerous_patterns.append(
                                            f"{py_file.relative_to(project_root)}:{line_num}: "
                                            f"F-string with backslash escape: {line.strip()}"
                                        )
                except Exception:
                    # Skip files that can't be read
                    pass

        assert (
            not dangerous_patterns
        ), f"REGRESSION ll_024: F-string backslash escapes found:\n" + "\n".join(
            dangerous_patterns
        )

    def test_all_python_files_compile(self, project_root: Path):
        """Ensure ALL Python files can be compiled (not just critical ones).

        This is the most comprehensive syntax check.
        """
        src_dir = project_root / "src"
        scripts_dir = project_root / "scripts"
        tests_dir = project_root / "tests"

        errors = []

        for directory in [src_dir, scripts_dir, tests_dir]:
            for py_file in directory.rglob("*.py"):
                # Skip __pycache__ and virtual environments
                if "__pycache__" in str(py_file) or ".venv" in str(py_file):
                    continue

                result = subprocess.run(
                    [sys.executable, "-m", "py_compile", str(py_file)],
                    capture_output=True,
                    text=True,
                )

                if result.returncode != 0:
                    errors.append(f"{py_file.relative_to(project_root)}: {result.stderr}")

        assert not errors, f"Compilation errors found:\n" + "\n".join(errors)

    def test_critical_imports_work(self, project_root: Path):
        """Verify critical imports don't raise ImportError or SyntaxError.

        This test catches issues that compile but fail at import time.
        """
        sys.path.insert(0, str(project_root))

        critical_imports = [
            ("src.orchestrator.main", "TradingOrchestrator"),
            ("src.execution.alpaca_executor", "AlpacaExecutor"),
            ("src.risk.trade_gateway", "TradeGateway"),
            ("src.agents.rl_agent", "RLFilter"),
            ("src.risk.position_manager", "PositionManager"),
        ]

        errors = []
        for module_name, class_name in critical_imports:
            try:
                module = __import__(module_name, fromlist=[class_name])
                getattr(module, class_name)
            except (ImportError, SyntaxError, AttributeError) as e:
                errors.append(f"{module_name}.{class_name}: {type(e).__name__}: {e}")

        assert (
            not errors
        ), f"Critical import errors found:\n" + "\n".join(errors)


class TestRuntimeVerification:
    """Tests that verify runtime health, not just syntax."""

    @pytest.fixture
    def project_root(self) -> Path:
        return Path(__file__).parent.parent

    def test_pre_merge_gate_executable(self, project_root: Path):
        """Ensure pre_merge_gate.py can be executed."""
        gate_script = project_root / "scripts" / "pre_merge_gate.py"

        # Just check if it's importable (running would require dependencies)
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(gate_script)],
            capture_output=True,
        )

        assert result.returncode == 0, f"pre_merge_gate.py failed to compile: {result.stderr}"

    def test_trading_orchestrator_instantiable(self, project_root: Path):
        """Verify TradingOrchestrator can be instantiated without crash.

        This catches initialization errors that syntax checks miss.
        """
        sys.path.insert(0, str(project_root))

        try:
            from src.orchestrator.main import TradingOrchestrator

            # Try to instantiate (may fail on missing env vars, but shouldn't crash)
            try:
                _ = TradingOrchestrator()
            except Exception as e:
                # Expected to fail without env vars, but should be a clean error
                assert "ALPACA_API_KEY" in str(e) or "environment" in str(
                    e
                ).lower(), f"Unexpected error during instantiation: {e}"
        except SyntaxError as e:
            pytest.fail(f"TradingOrchestrator has syntax error: {e}")

    def test_alpaca_executor_importable(self, project_root: Path):
        """Verify AlpacaExecutor can be imported (regression test for Dec 11).

        Dec 11, 2025: AlpacaExecutor had syntax error that broke all trading.
        """
        sys.path.insert(0, str(project_root))

        try:
            from src.execution.alpaca_executor import AlpacaExecutor

            # Verify class has expected methods
            expected_methods = ["submit_order", "get_positions", "close_position"]
            for method in expected_methods:
                assert hasattr(
                    AlpacaExecutor, method
                ), f"AlpacaExecutor missing method: {method}"

        except SyntaxError as e:
            pytest.fail(f"REGRESSION ll_009: AlpacaExecutor has syntax error: {e}")


class TestContinuousVerification:
    """Tests that would run continuously (daily/hourly)."""

    @pytest.fixture
    def project_root(self) -> Path:
        return Path(__file__).parent.parent

    def test_system_state_exists_and_valid(self, project_root: Path):
        """Verify system_state.json exists and is valid JSON."""
        state_file = project_root / "data" / "system_state.json"

        assert state_file.exists(), "system_state.json missing"

        import json

        try:
            with open(state_file, "r") as f:
                state = json.load(f)

            # Basic structure checks
            assert "meta" in state, "system_state missing 'meta' key"
            assert "account" in state, "system_state missing 'account' key"
            assert "strategies" in state, "system_state missing 'strategies' key"

        except json.JSONDecodeError as e:
            pytest.fail(f"system_state.json is invalid JSON: {e}")

    def test_trading_heartbeat_recent(self, project_root: Path):
        """Verify trading has attempted execution recently.

        Prevents silent trading halts like Dec 10-11 incident.
        """
        heartbeat_file = project_root / "data" / "trading_heartbeat.json"

        # This test only fails if heartbeat exists but is stale
        if heartbeat_file.exists():
            import json
            from datetime import datetime, timedelta

            with open(heartbeat_file, "r") as f:
                heartbeat = json.load(f)

            last_attempt = datetime.fromisoformat(heartbeat["timestamp"])
            age = datetime.utcnow() - last_attempt

            # Alert if no trading attempt in 3 days (accounting for weekends)
            assert age < timedelta(
                days=3
            ), f"Trading heartbeat stale: {age.days} days old (last: {last_attempt})"
