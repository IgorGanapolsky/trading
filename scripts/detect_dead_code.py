#!/usr/bin/env python3
"""Dead Code Detector.

Scans the codebase for potential dead code:
1. Functions/classes with 0 references
2. Files never imported
3. Deprecated markers
4. NotImplementedError patterns
5. Disabled feature flags
6. CRITICAL: Functions defined but never called (revenue-impacting)

Run as: python scripts/detect_dead_code.py
Or add to pre-commit: .pre-commit-config.yaml

Reference: rag_knowledge/lessons_learned/ll_014_dead_code_dynamic_budget_dec11.md
"""

import ast
import os
import re
import sys
from pathlib import Path
from typing import NamedTuple


class CriticalFunction(NamedTuple):
    """A function that MUST be called somewhere in the codebase."""

    file_path: str
    function_name: str
    description: str


# CRITICAL: Functions that must have call sites or system loses revenue
# Add new critical functions here when implementing revenue-impacting features
CRITICAL_FUNCTIONS = [
    CriticalFunction(
        "scripts/autonomous_trader.py",
        "_apply_dynamic_daily_budget",
        "Scales DAILY_INVESTMENT based on equity - without this, system stuck at $10/day",
    ),
    CriticalFunction(
        "src/analytics/options_profit_planner.py",
        "evaluate_theta_opportunity",
        "Evaluates theta harvest opportunities - core options revenue",
    ),
    CriticalFunction(
        "src/risk/risk_manager.py",
        "calculate_size",
        "Position sizing - without this, no trades execute",
    ),
]


# Directories to scan
SCAN_DIRS = ["src", "scripts"]
# Directories to ignore
IGNORE_DIRS = {"__pycache__", ".git", "venv", "node_modules", "data", "docs", "tests"}
# Files to ignore
IGNORE_FILES = {"__init__.py", "conftest.py"}


def find_python_files(base_path: str) -> list[Path]:
    """Find all Python files in the codebase."""
    files = []
    for scan_dir in SCAN_DIRS:
        dir_path = Path(base_path) / scan_dir
        if not dir_path.exists():
            continue
        for path in dir_path.rglob("*.py"):
            if any(ignore in path.parts for ignore in IGNORE_DIRS):
                continue
            if path.name in IGNORE_FILES:
                continue
            files.append(path)
    return files


def extract_definitions(file_path: Path) -> dict:
    """Extract function and class definitions from a file."""
    definitions = {"functions": [], "classes": []}
    try:
        with open(file_path) as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if not node.name.startswith("_"):  # Skip private
                    definitions["functions"].append(node.name)
            elif isinstance(node, ast.ClassDef):
                definitions["classes"].append(node.name)
    except Exception:
        pass
    return definitions


def find_references(files: list[Path], name: str) -> int:
    """Count references to a name across all files."""
    count = 0
    pattern = re.compile(rf"\b{re.escape(name)}\b")
    for file_path in files:
        try:
            content = file_path.read_text()
            matches = pattern.findall(content)
            count += len(matches)
        except Exception:
            pass
    return count


def find_deprecated_markers(files: list[Path]) -> list[tuple[Path, int, str]]:
    """Find files with DEPRECATED markers."""
    results = []
    patterns = [
        r"DEPRECATED",
        r"NotImplementedError",
        r"raise\s+NotImplementedError",
        r"TODO:\s*remove",
        r"BROKEN",
    ]
    for file_path in files:
        try:
            lines = file_path.read_text().splitlines()
            for i, line in enumerate(lines, 1):
                for pattern in patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        results.append((file_path, i, line.strip()[:80]))
                        break
        except Exception:
            pass
    return results


def find_disabled_features(files: list[Path]) -> list[tuple[Path, int, str]]:
    """Find feature flags defaulting to disabled."""
    results = []
    patterns = [
        r'os\.getenv\(["\'][A-Z_]+["\'],\s*["\']false["\']',
        r"ENABLED.*=.*False",
        r'ENABLE.*"false"',
    ]
    for file_path in files:
        try:
            lines = file_path.read_text().splitlines()
            for i, line in enumerate(lines, 1):
                for pattern in patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        results.append((file_path, i, line.strip()[:80]))
        except Exception:
            pass
    return results


def find_orphaned_files(base_path: str, files: list[Path]) -> list[Path]:
    """Find files that are never imported."""
    orphaned = []
    for file_path in files:
        module_name = file_path.stem
        if module_name.startswith("test_"):
            continue

        # Check if this module is imported anywhere
        import_patterns = [
            f"from {module_name}",
            f"import {module_name}",
            f"from .{module_name}",
            f"from src.{file_path.parent.name}.{module_name}",
        ]

        found = False
        for other_file in files:
            if other_file == file_path:
                continue
            try:
                content = other_file.read_text()
                for pattern in import_patterns:
                    if pattern in content:
                        found = True
                        break
            except Exception:
                pass
            if found:
                break

        if not found:
            orphaned.append(file_path)

    return orphaned


class FunctionCallVisitor(ast.NodeVisitor):
    """AST visitor that counts calls to specific functions."""

    def __init__(self, function_names: set[str]):
        self.function_names = function_names
        self.calls: dict[str, list[tuple[str, int]]] = {name: [] for name in function_names}
        self.current_file = ""

    def visit_Call(self, node: ast.Call):
        func_name = None
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        if func_name and func_name in self.function_names:
            self.calls[func_name].append((self.current_file, node.lineno))

        self.generic_visit(node)


def check_critical_function_coverage(base_path: str, files: list[Path]) -> list[CriticalFunction]:
    """
    Check that critical functions are actually called somewhere.

    This catches the pattern where a developer:
    1. Implements a function with great docstring
    2. Forgets to wire it into execution flow
    3. Feature silently never executes
    4. System loses money

    Returns list of dead critical functions.
    """
    function_names = {cf.function_name for cf in CRITICAL_FUNCTIONS}
    visitor = FunctionCallVisitor(function_names)

    # Scan all files for function calls
    for py_file in files:
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source)
            visitor.current_file = str(py_file)
            visitor.visit(tree)
        except (SyntaxError, UnicodeDecodeError):
            continue

    # Check which critical functions have no call sites
    dead_critical = []
    for cf in CRITICAL_FUNCTIONS:
        calls = visitor.calls.get(cf.function_name, [])
        if len(calls) == 0:
            # Verify function actually exists before flagging
            func_file = Path(base_path) / cf.file_path
            if func_file.exists():
                try:
                    source = func_file.read_text(encoding="utf-8")
                    tree = ast.parse(source)
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            if node.name == cf.function_name:
                                dead_critical.append(cf)
                                break
                except (SyntaxError, UnicodeDecodeError):
                    pass

    return dead_critical


def main():
    """Run dead code detection."""
    base_path = os.getcwd()
    files = find_python_files(base_path)

    print("=" * 70)
    print("DEAD CODE DETECTOR")
    print("=" * 70)
    print(f"Scanning {len(files)} Python files...\n")

    issues = []
    critical_dead = False

    # CRITICAL CHECK: Revenue-impacting functions must have call sites
    dead_critical_funcs = check_critical_function_coverage(base_path, files)
    if dead_critical_funcs:
        critical_dead = True
        print("CRITICAL: Revenue-impacting functions with NO CALL SITES:")
        for cf in dead_critical_funcs:
            print(f"   {cf.function_name}")
            print(f"      File: {cf.file_path}")
            print(f"      Impact: {cf.description}")
            issues.append(f"CRITICAL_DEAD: {cf.function_name}")
        print()
        print("   These functions are DEFINED but NEVER CALLED.")
        print("   The system will silently fail to use these features.")
        print("   See: rag_knowledge/lessons_learned/ll_014_dead_code_dynamic_budget_dec11.md")
        print()

    # Check for deprecated markers
    deprecated = find_deprecated_markers(files)
    if deprecated:
        print(f"⚠️  DEPRECATED/BROKEN markers found: {len(deprecated)}")
        for path, line, content in deprecated[:10]:
            print(f"   {path}:{line}: {content}")
            issues.append(f"DEPRECATED: {path}:{line}")
        if len(deprecated) > 10:
            print(f"   ... and {len(deprecated) - 10} more")
        print()

    # Check for disabled features
    disabled = find_disabled_features(files)
    if disabled:
        print(f"⚠️  Disabled feature flags found: {len(disabled)}")
        for path, line, content in disabled[:10]:
            print(f"   {path}:{line}: {content}")
            issues.append(f"DISABLED_FEATURE: {path}:{line}")
        if len(disabled) > 10:
            print(f"   ... and {len(disabled) - 10} more")
        print()

    # Check for orphaned files
    orphaned = find_orphaned_files(base_path, files)
    if orphaned:
        print(f"⚠️  Potentially orphaned files: {len(orphaned)}")
        for path in orphaned[:10]:
            print(f"   {path}")
            issues.append(f"ORPHANED: {path}")
        if len(orphaned) > 10:
            print(f"   ... and {len(orphaned) - 10} more")
        print()

    # Summary
    print("=" * 70)
    if critical_dead:
        print(f"COMMIT BLOCKED: {len(dead_critical_funcs)} critical functions are dead code")
        print("   Fix: Wire these functions into the execution flow")
        print("   These are revenue-impacting and MUST be called somewhere.")
        return 1
    elif issues:
        print(f"⚠️  Found {len(issues)} potential issues (non-blocking)")
        print("   Review and clean up dead code to maintain system health.")
        return 0  # Non-critical issues don't block
    else:
        print("✅ No dead code detected!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
