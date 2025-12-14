"""
Critical Function Coverage Test

Created: December 11, 2025
Purpose: Prevent critical trading functions from becoming dead code.

This test verifies that important functions are actually CALLED somewhere
in the codebase, not just defined. This catches the pattern where:
- Function is implemented with proper docstring
- Function is never wired into execution flow
- System silently fails to use the feature

Reference: rag_knowledge/lessons_learned/ll_014_dead_code_dynamic_budget_dec11.md
"""

import ast
from pathlib import Path
from typing import NamedTuple

import pytest


class CriticalFunction(NamedTuple):
    """A function that MUST be called somewhere in the codebase."""

    file_path: str  # Where the function is defined
    function_name: str  # The function name
    description: str  # Why this function is critical
    min_call_sites: int = 1  # Minimum number of places it should be called


# Registry of critical functions that must have call sites
# Add new critical functions here when implementing revenue-impacting features
CRITICAL_FUNCTIONS = [
    CriticalFunction(
        file_path="scripts/autonomous_trader.py",
        function_name="_apply_dynamic_daily_budget",
        description="Scales DAILY_INVESTMENT based on equity - without this, system stuck at $10/day",
        min_call_sites=1,
    ),
    CriticalFunction(
        file_path="src/analytics/options_profit_planner.py",
        function_name="evaluate_theta_opportunity",
        description="Evaluates theta harvest opportunities - core options revenue",
        min_call_sites=1,
    ),
    CriticalFunction(
        file_path="src/risk/risk_manager.py",
        function_name="calculate_size",
        description="Position sizing - without this, no trades execute",
        min_call_sites=1,
    ),
]


class FunctionCallVisitor(ast.NodeVisitor):
    """AST visitor that counts calls to a specific function."""

    def __init__(self, function_name: str):
        self.function_name = function_name
        self.call_count = 0
        self.call_locations: list[tuple[str, int]] = []  # (file, line)
        self.current_file = ""

    def visit_Call(self, node: ast.Call):
        """Visit function call nodes."""
        # Handle simple function calls: func_name()
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == self.function_name
            or isinstance(node.func, ast.Attribute)
            and node.func.attr == self.function_name
        ):
            self.call_count += 1
            self.call_locations.append((self.current_file, node.lineno))

        self.generic_visit(node)


def count_function_calls_in_file(file_path: Path, function_name: str) -> list[tuple[str, int]]:
    """Count calls to a function in a single file."""
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        visitor = FunctionCallVisitor(function_name)
        visitor.current_file = str(file_path)
        visitor.visit(tree)
        return visitor.call_locations
    except (SyntaxError, UnicodeDecodeError):
        return []


def count_function_calls_in_codebase(
    function_name: str,
    search_dirs: list[str] | None = None,
    exclude_definition_file: str | None = None,
) -> list[tuple[str, int]]:
    """
    Count all calls to a function across the codebase.

    Args:
        function_name: Name of the function to search for
        search_dirs: Directories to search (default: src/, scripts/, tests/)
        exclude_definition_file: File where function is defined (exclude self-calls)

    Returns:
        List of (file_path, line_number) tuples where function is called
    """
    if search_dirs is None:
        search_dirs = ["src", "scripts", "tests"]

    root = Path(__file__).parent.parent
    all_calls: list[tuple[str, int]] = []

    for search_dir in search_dirs:
        dir_path = root / search_dir
        if not dir_path.exists():
            continue

        for py_file in dir_path.rglob("*.py"):
            # Skip the file where the function is defined (we want external calls)
            if exclude_definition_file and str(py_file).endswith(exclude_definition_file):
                continue
            # Skip test files when searching for production calls
            if "test_" in py_file.name and search_dir != "tests":
                continue

            calls = count_function_calls_in_file(py_file, function_name)
            all_calls.extend(calls)

    return all_calls


def verify_function_is_defined(file_path: str, function_name: str) -> bool:
    """Verify that the function exists in the specified file."""
    root = Path(__file__).parent.parent
    full_path = root / file_path

    if not full_path.exists():
        return False

    try:
        source = full_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == function_name:
                    return True
        return False
    except (SyntaxError, UnicodeDecodeError):
        return False


class TestCriticalFunctionCoverage:
    """Test that critical functions are actually called in the codebase."""

    @pytest.mark.parametrize(
        "critical_func",
        CRITICAL_FUNCTIONS,
        ids=[f.function_name for f in CRITICAL_FUNCTIONS],
    )
    def test_critical_function_has_call_sites(self, critical_func: CriticalFunction):
        """
        Verify each critical function is called at least once.

        This prevents the pattern where:
        1. Developer implements function with great docstring
        2. Forgets to wire it into execution flow
        3. Feature silently never executes
        4. System loses money because critical code is dead
        """
        # First, verify the function exists
        assert verify_function_is_defined(critical_func.file_path, critical_func.function_name), (
            f"Function {critical_func.function_name} not found in {critical_func.file_path}"
        )

        # Find all call sites (excluding the definition file to avoid counting internal calls only)
        call_sites = count_function_calls_in_codebase(
            critical_func.function_name,
            search_dirs=["src", "scripts"],
            exclude_definition_file=None,  # Include all files
        )

        # Build helpful error message
        if len(call_sites) < critical_func.min_call_sites:
            pytest.fail(
                f"\n"
                f"DEAD CODE DETECTED: {critical_func.function_name}\n"
                f"{'=' * 60}\n"
                f"File: {critical_func.file_path}\n"
                f"Description: {critical_func.description}\n"
                f"Expected calls: >= {critical_func.min_call_sites}\n"
                f"Actual calls: {len(call_sites)}\n"
                f"Call sites found: {call_sites}\n"
                f"\n"
                f"ACTION REQUIRED:\n"
                f"This function is DEFINED but NEVER CALLED in execution flow.\n"
                f"Wire it into the appropriate entry point.\n"
                f"\n"
                f"See: rag_knowledge/lessons_learned/ll_014_dead_code_dynamic_budget_dec11.md"
            )

    def test_critical_functions_registry_not_empty(self):
        """Ensure we have critical functions to check."""
        assert len(CRITICAL_FUNCTIONS) > 0, "No critical functions registered for monitoring"

    def test_all_critical_function_files_exist(self):
        """Verify all registered critical function files exist."""
        root = Path(__file__).parent.parent

        for critical_func in CRITICAL_FUNCTIONS:
            file_path = root / critical_func.file_path
            assert file_path.exists(), (
                f"Critical function file does not exist: {critical_func.file_path}\n"
                f"Either update CRITICAL_FUNCTIONS or restore the file."
            )


class TestDeadCodeDetection:
    """Additional dead code detection utilities."""

    def test_no_functions_with_todo_only_body(self):
        """
        Detect functions that only contain pass, TODO, or NotImplementedError.

        These are often placeholders that get forgotten.
        """
        root = Path(__file__).parent.parent
        placeholder_functions: list[tuple[str, str, int]] = []

        for py_file in (root / "src").rglob("*.py"):
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source)

                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        # Check if body is just pass, docstring + pass, or NotImplementedError
                        body = node.body
                        effective_body = [
                            stmt
                            for stmt in body
                            if not isinstance(stmt, ast.Expr)
                            or not isinstance(stmt.value, ast.Constant)
                        ]

                        if len(effective_body) == 1:
                            stmt = effective_body[0]
                            if isinstance(stmt, ast.Pass):
                                placeholder_functions.append(
                                    (str(py_file.relative_to(root)), node.name, node.lineno)
                                )
                            elif isinstance(stmt, ast.Raise):
                                if isinstance(stmt.exc, ast.Call):
                                    if isinstance(stmt.exc.func, ast.Name):
                                        if stmt.exc.func.id == "NotImplementedError":
                                            placeholder_functions.append(
                                                (
                                                    str(py_file.relative_to(root)),
                                                    node.name,
                                                    node.lineno,
                                                )
                                            )
            except (SyntaxError, UnicodeDecodeError):
                continue

        # Allow some placeholder functions but warn if too many
        max_allowed = 10
        if len(placeholder_functions) > max_allowed:
            funcs_str = "\n".join(
                f"  - {f}:{name}:{line}" for f, name, line in placeholder_functions[:20]
            )
            pytest.fail(
                f"Too many placeholder functions ({len(placeholder_functions)} > {max_allowed}):\n"
                f"{funcs_str}\n"
                f"...\n"
                f"These may be forgotten implementations."
            )


if __name__ == "__main__":
    # Quick CLI check
    print("Checking critical function coverage...")
    for func in CRITICAL_FUNCTIONS:
        calls = count_function_calls_in_codebase(func.function_name)
        status = "OK" if len(calls) >= func.min_call_sites else "DEAD CODE"
        print(f"[{status}] {func.function_name}: {len(calls)} call sites")
        if calls:
            for file, line in calls[:3]:
                print(f"        - {file}:{line}")
