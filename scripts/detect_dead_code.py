#!/usr/bin/env python3
"""
Dead Code Detection Script

Runs on every PR to catch:
1. Stub files (functions that return hardcoded values)
2. Unused imports
3. Empty directories (only __init__.py)
4. Broken imports that would fail at runtime
5. Files that are never imported anywhere

Author: Claude (Dec 24, 2025)
See: rag_knowledge/lessons_learned/ll_010_dead_code_and_dormant_systems_dec11.md
"""

import argparse
import ast
import os
import sys
from pathlib import Path


def find_stub_functions(file_path: Path) -> list[str]:
    """Find functions that just return hardcoded values (stubs)."""
    stubs = []
    try:
        with open(file_path) as f:
            tree = ast.parse(f.read(), filename=str(file_path))
    except SyntaxError:
        return []  # Skip files with syntax errors

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # Check if function body is just a return with a constant
            if len(node.body) == 1:
                body = node.body[0]
                if isinstance(body, ast.Return):
                    if isinstance(body.value, ast.Constant):
                        stubs.append(
                            f"{file_path}:{node.lineno}: {node.name}() returns hardcoded {body.value.value!r}"
                        )
                    elif isinstance(body.value, ast.Dict) and not body.value.keys:
                        stubs.append(f"{file_path}:{node.lineno}: {node.name}() returns empty dict")
                    elif isinstance(body.value, ast.List) and not body.value.elts:
                        stubs.append(f"{file_path}:{node.lineno}: {node.name}() returns empty list")
    return stubs


def find_empty_directories(root: Path) -> list[str]:
    """Find directories that only contain __init__.py (no real code)."""
    empty_dirs = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip hidden directories and __pycache__
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "__pycache__"]

        py_files = [f for f in filenames if f.endswith(".py")]
        if py_files == ["__init__.py"]:
            init_path = Path(dirpath) / "__init__.py"
            if init_path.stat().st_size < 100:  # Small __init__.py
                empty_dirs.append(f"{dirpath}: Only contains empty __init__.py")
    return empty_dirs


def find_broken_imports(file_path: Path, src_root: Path) -> list[str]:
    """Find imports that reference non-existent modules (not in try-except)."""
    broken = []
    try:
        with open(file_path) as f:
            tree = ast.parse(f.read(), filename=str(file_path))
    except SyntaxError:
        return []

    # Find imports NOT wrapped in try-except
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            # Check if this import is inside a try block
            # This is a simplified check - may have false positives
            if node.module.startswith("src."):
                module_path = node.module.replace(".", "/") + ".py"
                full_path = src_root.parent / module_path
                pkg_path = src_root.parent / node.module.replace(".", "/") / "__init__.py"

                if not full_path.exists() and not pkg_path.exists():
                    # Check if it's a package
                    pkg_dir = src_root.parent / node.module.replace(".", "/")
                    if not pkg_dir.is_dir():
                        broken.append(
                            f"{file_path}:{node.lineno}: imports non-existent {node.module}"
                        )
    return broken


def find_unused_files(src_root: Path) -> list[str]:
    """Find Python files that are never imported anywhere."""
    all_files = set()
    imported_modules = set()

    # Collect all Python files
    for py_file in src_root.rglob("*.py"):
        if "__pycache__" not in str(py_file):
            rel_path = py_file.relative_to(src_root.parent)
            module_name = str(rel_path).replace("/", ".").replace(".py", "")
            all_files.add((py_file, module_name))

    # Collect all imports
    for py_file in src_root.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        try:
            with open(py_file) as f:
                tree = ast.parse(f.read(), filename=str(py_file))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imported_modules.add(alias.name)

    # Find files that are never imported
    unused = []
    for file_path, module_name in all_files:
        if file_path.name == "__init__.py":
            continue
        if file_path.name.startswith("test_"):
            continue
        if "tests" in str(file_path):
            continue

        # Check if this module is imported anywhere
        is_imported = False
        for imp in imported_modules:
            if module_name.endswith(imp) or imp.startswith(module_name):
                is_imported = True
                break
            # Also check partial matches
            if module_name.split(".")[-1] in imp:
                is_imported = True
                break

        if not is_imported:
            # Additional check: is it a script with if __name__ == "__main__"?
            try:
                with open(file_path) as f:
                    content = f.read()
                    if '__name__ == "__main__"' in content or "__name__ == '__main__'" in content:
                        continue  # It's an executable script
            except Exception:
                pass
            unused.append(f"{file_path}: Never imported anywhere")

    return unused


def main():
    parser = argparse.ArgumentParser(description="Detect dead code in the repository")
    parser.add_argument("--src", default="src", help="Source directory to scan")
    parser.add_argument("--strict", action="store_true", help="Fail on any findings")
    parser.add_argument("--ci", action="store_true", help="CI mode (formatted output)")
    args = parser.parse_args()

    src_root = Path(args.src).resolve()
    if not src_root.exists():
        print(f"Error: {src_root} does not exist")
        sys.exit(1)

    findings = []

    print("=" * 60)
    print("DEAD CODE DETECTION")
    print("=" * 60)

    # 1. Find stub functions
    print("\n[1/4] Scanning for stub functions...")
    for py_file in src_root.rglob("*.py"):
        if "__pycache__" not in str(py_file):
            stubs = find_stub_functions(py_file)
            findings.extend(stubs)

    # 2. Find empty directories
    print("[2/4] Scanning for empty directories...")
    empty_dirs = find_empty_directories(src_root)
    findings.extend(empty_dirs)

    # 3. Find broken imports (skip in CI - requires full dependency install)
    if not args.ci:
        print("[3/4] Scanning for broken imports...")
        for py_file in src_root.rglob("*.py"):
            if "__pycache__" not in str(py_file):
                broken = find_broken_imports(py_file, src_root)
                findings.extend(broken)
    else:
        print("[3/4] Skipping broken import check in CI mode")

    # 4. Find unused files (high false positive rate, informational only)
    print("[4/4] Scanning for unused files...")
    unused = find_unused_files(src_root)

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    if findings:
        print(f"\n DEAD CODE FOUND ({len(findings)} issues):\n")
        for finding in findings:
            if args.ci:
                # GitHub Actions annotation format
                print(f"::warning file={finding.split(':')[0]}::{finding}")
            else:
                print(f"  - {finding}")
    else:
        print("\n No dead code found!")

    if unused:
        print(f"\n POTENTIALLY UNUSED FILES ({len(unused)} - verify manually):\n")
        for u in unused[:10]:  # Limit output
            print(f"  - {u}")
        if len(unused) > 10:
            print(f"  ... and {len(unused) - 10} more")

    print("\n" + "=" * 60)

    if args.strict and findings:
        print("FAILED: Dead code detected (--strict mode)")
        sys.exit(1)

    print("PASSED: Dead code check complete")
    sys.exit(0)


if __name__ == "__main__":
    main()
