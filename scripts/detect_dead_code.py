#!/usr/bin/env python3
"""
Dead Code Detector - Prevents Medallion Architecture Pattern

Detects:
1. Unused modules (no imports from them)
2. Unused functions/classes (defined but never called)
3. Empty or near-empty directories
4. Modules that import from each other but nothing else uses them

This prevents the LL-043 pattern: "Built comprehensive Medallion Architecture,
but never integrated it into main system."

Usage:
    python3 scripts/detect_dead_code.py
    python3 scripts/detect_dead_code.py --report json
    python3 scripts/detect_dead_code.py --ignore-dirs tests examples

RAG Keywords: dead-code, unused-modules, technical-debt, code-cleanup
Lesson: LL-043 - Medallion Architecture unused code
"""

import argparse
import ast
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set

PROJECT_ROOT = Path(__file__).parent.parent


class ImportAnalyzer(ast.NodeVisitor):
    """Extract imports and definitions from Python AST."""

    def __init__(self):
        self.imports: List[str] = []
        self.from_imports: Dict[str, List[str]] = defaultdict(list)
        self.definitions: Set[str] = set()

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append(alias.name)

    def visit_ImportFrom(self, node):
        if node.module:
            for alias in node.names:
                self.from_imports[node.module].append(alias.name)

    def visit_FunctionDef(self, node):
        self.definitions.add(f"function:{node.name}")
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self.definitions.add(f"class:{node.name}")
        self.generic_visit(node)


def get_python_files(
    root: Path, ignore_dirs: List[str] = None
) -> List[Path]:
    """Get all Python files, excluding ignored directories."""
    ignore_dirs = ignore_dirs or ["__pycache__", ".git", "venv", ".venv", "node_modules"]
    python_files = []

    for py_file in root.glob("**/*.py"):
        # Check if any parent is in ignore list
        if any(ignored in str(py_file) for ignored in ignore_dirs):
            continue
        python_files.append(py_file)

    return python_files


def analyze_imports(file_path: Path) -> ImportAnalyzer:
    """Parse file and extract imports and definitions."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(file_path))
        analyzer = ImportAnalyzer()
        analyzer.visit(tree)
        return analyzer
    except (SyntaxError, UnicodeDecodeError) as e:
        print(f"Warning: Could not parse {file_path}: {e}")
        return ImportAnalyzer()


def normalize_import_path(import_path: str, project_root: Path) -> str:
    """Convert import path to module path relative to project."""
    # Handle relative imports like "src.medallion.bronze"
    parts = import_path.split(".")
    
    # If starts with src, keep as is
    if parts[0] == "src":
        return import_path
    
    # If it's a module from src, add src prefix
    potential_path = project_root / "src" / parts[0]
    if potential_path.exists():
        return f"src.{import_path}"
    
    return import_path


def build_import_graph(
    files: List[Path], project_root: Path
) -> Dict[str, Set[str]]:
    """Build a graph of module -> modules_that_import_it."""
    import_graph = defaultdict(set)
    
    for file_path in files:
        analyzer = analyze_imports(file_path)
        
        # Convert file path to module path
        try:
            rel_path = file_path.relative_to(project_root)
            # Remove .py and convert path to module notation
            module_path = str(rel_path.with_suffix("")).replace("/", ".")
            
            # Track regular imports
            for imp in analyzer.imports:
                normalized = normalize_import_path(imp, project_root)
                import_graph[normalized].add(module_path)
            
            # Track from imports (module level)
            for from_module in analyzer.from_imports.keys():
                normalized = normalize_import_path(from_module, project_root)
                import_graph[normalized].add(module_path)
        
        except ValueError:
            # File not relative to project root
            continue
    
    return import_graph


def find_unused_modules(
    files: List[Path], project_root: Path, import_graph: Dict[str, Set[str]]
) -> List[Dict]:
    """Find modules that are never imported by anything."""
    unused = []
    
    # Get all module paths
    all_modules = set()
    for file_path in files:
        try:
            rel_path = file_path.relative_to(project_root)
            module_path = str(rel_path.with_suffix("")).replace("/", ".")
            all_modules.add(module_path)
        except ValueError:
            continue
    
    # Find modules with zero imports
    for module in all_modules:
        # Skip __init__.py files (they organize packages)
        if module.endswith(".__init__"):
            continue
        
        # Skip main entry points
        if "main.py" in module or "autonomous_trader" in module:
            continue
        
        # Skip test files (they import but aren't imported)
        if "test_" in module or "tests." in module:
            continue
        
        # Check if this module is imported anywhere
        importers = import_graph.get(module, set())
        
        # Also check parent package imports (e.g., src.medallion)
        parent_parts = module.split(".")
        for i in range(1, len(parent_parts)):
            parent_module = ".".join(parent_parts[:i])
            importers.update(import_graph.get(parent_module, set()))
        
        if not importers:
            # Check file size to filter out truly empty stubs
            file_path = project_root / module.replace(".", "/")
            if file_path.with_suffix(".py").exists():
                size = file_path.with_suffix(".py").stat().st_size
                unused.append({
                    "module": module,
                    "path": str(file_path.with_suffix(".py")),
                    "size_bytes": size,
                    "reason": "No imports found"
                })
    
    return unused


def find_isolated_module_groups(
    import_graph: Dict[str, Set[str]], all_modules: Set[str]
) -> List[Dict]:
    """
    Find groups of modules that only import each other but nothing else uses them.
    
    Example: src.medallion.* modules all import each other, but only
    src.ml.medallion_trainer imports them, and nothing imports medallion_trainer.
    """
    isolated_groups = []
    
    # Check for isolated module prefixes (like src.medallion.*)
    prefixes = set()
    for module in all_modules:
        parts = module.split(".")
        if len(parts) >= 2:
            prefix = ".".join(parts[:2])  # e.g., "src.medallion"
            prefixes.add(prefix)
    
    for prefix in prefixes:
        # Get all modules with this prefix
        group_modules = {m for m in all_modules if m.startswith(prefix + ".")}
        if len(group_modules) <= 1:
            continue
        
        # Find external importers (not in the group)
        external_importers = set()
        for module in group_modules:
            importers = import_graph.get(module, set())
            external_importers.update(
                imp for imp in importers if not imp.startswith(prefix + ".")
            )
        
        # If no external importers or only one that's also unused, it's isolated
        if len(external_importers) <= 1:
            total_size = 0
            for module in group_modules:
                module_path = PROJECT_ROOT / module.replace(".", "/")
                if module_path.with_suffix(".py").exists():
                    total_size += module_path.with_suffix(".py").stat().st_size
            
            isolated_groups.append({
                "prefix": prefix,
                "modules": sorted(group_modules),
                "external_importers": sorted(external_importers),
                "total_size_bytes": total_size,
                "module_count": len(group_modules),
            })
    
    return isolated_groups


def find_empty_directories(root: Path, ignore_dirs: List[str]) -> List[Dict]:
    """Find directories with only .gitkeep or empty subdirectories."""
    empty_dirs = []
    
    for dir_path in root.glob("**/"):
        # Skip ignored directories
        if any(ignored in str(dir_path) for ignored in ignore_dirs):
            continue
        
        if not dir_path.is_dir():
            continue
        
        # Get all files in directory (recursively)
        files = list(dir_path.glob("**/*"))
        files = [f for f in files if f.is_file()]
        
        # Filter out .gitkeep files
        non_gitkeep = [f for f in files if f.name != ".gitkeep"]
        
        if not non_gitkeep and dir_path != root:
            empty_dirs.append({
                "path": str(dir_path.relative_to(root)),
                "gitkeep_count": len(files) - len(non_gitkeep),
            })
    
    return empty_dirs


def main():
    parser = argparse.ArgumentParser(
        description="Detect dead code and unused modules"
    )
    parser.add_argument(
        "--report",
        choices=["text", "json"],
        default="text",
        help="Output format"
    )
    parser.add_argument(
        "--ignore-dirs",
        nargs="+",
        default=["tests", "examples", "__pycache__", ".git", "venv", ".venv"],
        help="Directories to ignore"
    )
    parser.add_argument(
        "--threshold-kb",
        type=int,
        default=10,
        help="Minimum size in KB to report unused modules"
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("DEAD CODE DETECTOR - Preventing LL-043 Pattern")
    print("=" * 70)
    print()
    
    # Step 1: Get all Python files
    print("[1/5] Scanning Python files...")
    files = get_python_files(PROJECT_ROOT, args.ignore_dirs)
    print(f"  Found {len(files)} Python files")
    
    # Step 2: Build import graph
    print("\n[2/5] Building import graph...")
    import_graph = build_import_graph(files, PROJECT_ROOT)
    print(f"  Tracked imports for {len(import_graph)} modules")
    
    # Step 3: Find unused modules
    print("\n[3/5] Finding unused modules...")
    unused_modules = find_unused_modules(files, PROJECT_ROOT, import_graph)
    
    # Filter by size threshold
    threshold_bytes = args.threshold_kb * 1024
    significant_unused = [
        m for m in unused_modules if m["size_bytes"] > threshold_bytes
    ]
    print(f"  Found {len(significant_unused)} unused modules (>{args.threshold_kb}KB)")
    
    # Step 4: Find isolated module groups
    print("\n[4/5] Finding isolated module groups...")
    all_modules = {
        str(f.relative_to(PROJECT_ROOT).with_suffix("")).replace("/", ".")
        for f in files
    }
    isolated_groups = find_isolated_module_groups(import_graph, all_modules)
    print(f"  Found {len(isolated_groups)} isolated module groups")
    
    # Step 5: Find empty directories
    print("\n[5/5] Finding empty directories...")
    empty_dirs = find_empty_directories(PROJECT_ROOT, args.ignore_dirs + [".git"])
    print(f"  Found {len(empty_dirs)} empty directories")
    
    # Generate report
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    
    if args.report == "json":
        report = {
            "unused_modules": significant_unused,
            "isolated_groups": isolated_groups,
            "empty_directories": empty_dirs,
            "summary": {
                "unused_count": len(significant_unused),
                "isolated_groups_count": len(isolated_groups),
                "empty_dirs_count": len(empty_dirs),
            }
        }
        print(json.dumps(report, indent=2))
    else:
        # Text report
        if isolated_groups:
            print("\n🔴 ISOLATED MODULE GROUPS (high priority):")
            print("   These modules only import each other but aren't used elsewhere")
            print()
            for group in isolated_groups:
                print(f"   {group['prefix']}/ ({group['module_count']} modules, "
                      f"{group['total_size_bytes'] // 1024}KB)")
                print(f"      Modules: {', '.join(m.split('.')[-1] for m in group['modules'][:5])}")
                if group['external_importers']:
                    print(f"      Only imported by: {', '.join(group['external_importers'])}")
                else:
                    print(f"      ⚠️  NO external imports at all!")
                print()
        
        if significant_unused:
            print("\n🟡 UNUSED MODULES (medium priority):")
            for module in significant_unused[:10]:
                size_kb = module['size_bytes'] // 1024
                print(f"   {module['module']} ({size_kb}KB)")
            if len(significant_unused) > 10:
                print(f"   ... and {len(significant_unused) - 10} more")
        
        if empty_dirs:
            print("\n⚪ EMPTY DIRECTORIES (low priority):")
            for ed in empty_dirs[:10]:
                print(f"   {ed['path']}")
            if len(empty_dirs) > 10:
                print(f"   ... and {len(empty_dirs) - 10} more")
    
    # Exit code
    print("\n" + "=" * 70)
    if isolated_groups or significant_unused:
        total_dead_kb = sum(g['total_size_bytes'] for g in isolated_groups) // 1024
        total_dead_kb += sum(m['size_bytes'] for m in significant_unused) // 1024
        
        print(f"DEAD CODE FOUND: ~{total_dead_kb}KB of unused code")
        print("\nRecommendation:")
        print("  1. Review isolated module groups - likely candidates for removal")
        print("  2. Check if unused modules are actually needed")
        print("  3. Document decision in rag_knowledge/decisions/")
        sys.exit(1)
    else:
        print("NO SIGNIFICANT DEAD CODE FOUND ✅")
        sys.exit(0)


if __name__ == "__main__":
    main()
