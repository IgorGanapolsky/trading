#!/usr/bin/env python3
"""
Pre-Cleanup Safety Check - Run BEFORE deleting any code.

Prevents breaking the system by checking:
1. Import dependencies - who imports the module you're deleting?
2. Test dependencies - are there tests for this module?
3. Config references - does any config reference this?

Usage:
    python3 scripts/pre_cleanup_check.py src/risk/kelly.py
    python3 scripts/pre_cleanup_check.py src/rag/  # Check entire directory

Created: Jan 12, 2026
Lesson: PR #1445 deleted modules without checking imports, broke CI.
"""

import subprocess
import sys
from pathlib import Path


def find_imports(module_path: str) -> dict:
    """Find all files that import from the given module."""
    results = {"imports": [], "tests": [], "scripts": [], "configs": []}

    # Convert path to import format
    # src/risk/kelly.py -> src.risk.kelly or src/risk/ -> src.risk
    module_path = module_path.rstrip("/")
    if module_path.endswith(".py"):
        module_path = module_path[:-3]
    import_pattern = module_path.replace("/", ".")

    # Also check for partial imports (from src.risk import kelly)
    parts = import_pattern.split(".")
    parent_pattern = ".".join(parts[:-1]) if len(parts) > 1 else import_pattern
    module_name = parts[-1] if len(parts) > 1 else ""

    print(f"Checking imports for: {import_pattern}")
    print(f"Parent pattern: {parent_pattern}")
    print("-" * 60)

    # Search for imports
    try:
        # Direct imports: from src.risk.kelly import ...
        result = subprocess.run(
            ["grep", "-r", f"from {import_pattern}", "--include=*.py",
             "--exclude=pre_cleanup_check.py", "."],
            capture_output=True, text=True
        )
        for line in result.stdout.strip().split("\n"):
            if line:
                filepath = line.split(":")[0]
                if "/tests/" in filepath or filepath.startswith("./tests/"):
                    results["tests"].append(line)
                elif "/scripts/" in filepath or filepath.startswith("./scripts/"):
                    results["scripts"].append(line)
                else:
                    results["imports"].append(line)

        # Import from parent: from src.risk import kelly
        if module_name:
            result = subprocess.run(
                ["grep", "-r", f"from {parent_pattern} import.*{module_name}", "--include=*.py", "."],
                capture_output=True, text=True
            )
            for line in result.stdout.strip().split("\n"):
                if line and line not in results["imports"]:
                    filepath = line.split(":")[0]
                    if "/tests/" in filepath or filepath.startswith("./tests/"):
                        results["tests"].append(line)
                    elif "/scripts/" in filepath or filepath.startswith("./scripts/"):
                        results["scripts"].append(line)
                    else:
                        results["imports"].append(line)

        # Check config files
        result = subprocess.run(
            ["grep", "-r", import_pattern, "--include=*.json", "--include=*.yaml", "--include=*.yml", "."],
            capture_output=True, text=True
        )
        for line in result.stdout.strip().split("\n"):
            if line:
                results["configs"].append(line)

    except Exception as e:
        print(f"Error searching: {e}")

    return results


def print_results(results: dict, module_path: str):
    """Print results with recommendations."""
    total_deps = len(results["imports"]) + len(results["tests"]) + len(results["scripts"])

    print("\n" + "=" * 60)
    print(f"CLEANUP SAFETY CHECK: {module_path}")
    print("=" * 60)

    if results["imports"]:
        print(f"\n❌ BLOCKING: {len(results['imports'])} source file(s) import this module:")
        for imp in results["imports"][:10]:
            print(f"   {imp}")
        if len(results["imports"]) > 10:
            print(f"   ... and {len(results['imports']) - 10} more")
        print("\n   ACTION: Create stub file OR update these imports first")

    if results["tests"]:
        print(f"\n⚠️  WARNING: {len(results['tests'])} test file(s) import this module:")
        for test in results["tests"][:5]:
            print(f"   {test}")
        if len(results["tests"]) > 5:
            print(f"   ... and {len(results['tests']) - 5} more")
        print("\n   ACTION: Delete these tests BEFORE deleting the module")

    if results["scripts"]:
        print(f"\n⚠️  WARNING: {len(results['scripts'])} script(s) import this module:")
        for script in results["scripts"][:5]:
            print(f"   {script}")
        print("\n   ACTION: Update scripts OR create stub")

    if results["configs"]:
        print(f"\n⚠️  WARNING: {len(results['configs'])} config(s) reference this module:")
        for config in results["configs"][:5]:
            print(f"   {config}")

    print("\n" + "-" * 60)
    if total_deps == 0:
        print("✅ SAFE TO DELETE - No dependencies found")
    else:
        print(f"❌ NOT SAFE - {total_deps} dependencies must be handled first")
        print("\nCleanup Checklist:")
        print("1. [ ] Delete or update test files that import this module")
        print("2. [ ] Create stub file if source files depend on it")
        print("3. [ ] Update scripts that import this module")
        print("4. [ ] Run: python3 scripts/system_health_check.py")
        print("5. [ ] Run: pytest tests/ -x --tb=short")
    print("-" * 60)

    return total_deps == 0


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/pre_cleanup_check.py <module_path>")
        print("Example: python3 scripts/pre_cleanup_check.py src/risk/kelly.py")
        sys.exit(1)

    module_path = sys.argv[1]

    # Handle directory paths
    if Path(module_path).is_dir():
        print(f"Checking directory: {module_path}")
        all_safe = True
        for py_file in Path(module_path).rglob("*.py"):
            if py_file.name != "__init__.py":
                results = find_imports(str(py_file))
                safe = print_results(results, str(py_file))
                if not safe:
                    all_safe = False

        if all_safe:
            print("\n✅ ALL FILES IN DIRECTORY SAFE TO DELETE")
        else:
            print("\n❌ SOME FILES HAVE DEPENDENCIES - FIX BEFORE DELETING")
            sys.exit(1)
    else:
        results = find_imports(module_path)
        safe = print_results(results, module_path)
        if not safe:
            sys.exit(1)


if __name__ == "__main__":
    main()
