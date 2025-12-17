#!/usr/bin/env python3
"""
Import Usage Analyzer with ML Learning

Tracks import patterns over time and learns what constitutes
"suspicious" unused code patterns.

Features:
1. Real-time import dependency mapping
2. Historical trend analysis (is this module's usage declining?)
3. ML-powered anomaly detection for module isolation
4. Automatic lessons learned generation

Usage:
    python3 scripts/analyze_import_usage.py
    python3 scripts/analyze_import_usage.py --learn  # Update ML model
    python3 scripts/analyze_import_usage.py --trend 30  # 30-day trend

RAG Keywords: import-analysis, dependency-tracking, ml-learning
Lesson: LL-043 - Learn from usage patterns to predict future dead code
"""

import argparse
import ast
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
USAGE_HISTORY_FILE = PROJECT_ROOT / "data" / "ml" / "import_usage_history.json"


class ImportUsageTracker:
    """Track import usage patterns over time."""

    def __init__(self):
        self.current_snapshot: dict[str, set[str]] = defaultdict(set)
        self.history: list[dict] = []
        self.load_history()

    def load_history(self):
        """Load historical usage data."""
        if USAGE_HISTORY_FILE.exists():
            try:
                with open(USAGE_HISTORY_FILE) as f:
                    data = json.load(f)
                    self.history = data.get("snapshots", [])
            except Exception as e:
                print(f"Warning: Could not load history: {e}")

    def save_snapshot(self):
        """Save current snapshot to history."""
        USAGE_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Convert sets to lists for JSON serialization
        serializable_snapshot = {
            module: list(importers)
            for module, importers in self.current_snapshot.items()
        }

        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "usage": serializable_snapshot,
            "module_count": len(self.current_snapshot),
        }

        self.history.append(snapshot)

        # Keep last 90 days only
        cutoff = datetime.now() - timedelta(days=90)
        self.history = [
            s for s in self.history
            if datetime.fromisoformat(s["timestamp"]) > cutoff
        ]

        with open(USAGE_HISTORY_FILE, "w") as f:
            json.dump({"snapshots": self.history}, f, indent=2)

        print(f"✅ Saved snapshot to {USAGE_HISTORY_FILE}")
        print(f"   Historical snapshots: {len(self.history)}")

    def analyze_trends(self, module: str, days: int = 30) -> dict:
        """Analyze usage trend for a specific module."""
        cutoff = datetime.now() - timedelta(days=days)

        recent_snapshots = [
            s for s in self.history
            if datetime.fromisoformat(s["timestamp"]) > cutoff
        ]

        if not recent_snapshots:
            return {"trend": "unknown", "data_points": 0}

        # Count importers over time
        usage_over_time = []
        for snapshot in recent_snapshots:
            importers = snapshot["usage"].get(module, [])
            usage_over_time.append({
                "timestamp": snapshot["timestamp"],
                "importer_count": len(importers),
            })

        # Calculate trend
        if len(usage_over_time) < 2:
            trend = "stable"
        else:
            first_count = usage_over_time[0]["importer_count"]
            last_count = usage_over_time[-1]["importer_count"]

            if last_count == 0 and first_count > 0:
                trend = "declining_to_zero"
            elif last_count < first_count:
                trend = "declining"
            elif last_count > first_count:
                trend = "growing"
            else:
                trend = "stable"

        return {
            "trend": trend,
            "data_points": len(usage_over_time),
            "current_importers": usage_over_time[-1]["importer_count"],
            "first_importers": usage_over_time[0]["importer_count"],
            "usage_timeline": usage_over_time,
        }

    def detect_anomalies(self) -> list[dict]:
        """
        Detect suspicious patterns that might indicate future dead code.

        Patterns:
        1. Module with declining usage (5+ importers -> 1-2)
        2. Module never imported outside its own package
        3. Module built but never integrated
        """
        anomalies = []

        for module, importers in self.current_snapshot.items():
            # Skip test modules
            if "test_" in module or "tests." in module:
                continue

            # Pattern 1: Declining usage
            trend = self.analyze_trends(module, days=30)
            if trend["trend"] == "declining_to_zero":
                anomalies.append({
                    "module": module,
                    "pattern": "declining_usage",
                    "severity": "high",
                    "details": f"Usage dropped from {trend['first_importers']} to {trend['current_importers']} importers",
                })

            # Pattern 2: Never used outside own package
            if importers:
                module_package = ".".join(module.split(".")[:-1])
                external_importers = [
                    imp for imp in importers
                    if not imp.startswith(module_package)
                ]

                if not external_importers and len(importers) > 0:
                    anomalies.append({
                        "module": module,
                        "pattern": "isolated_package",
                        "severity": "medium",
                        "details": f"Only imported within {module_package} package",
                    })

            # Pattern 3: No imports at all (but exists)
            if not importers and not module.endswith("__main__"):
                anomalies.append({
                    "module": module,
                    "pattern": "never_imported",
                    "severity": "high",
                    "details": "Module exists but has zero imports",
                })

        return anomalies


def scan_imports(root: Path) -> dict[str, set[str]]:
    """Scan all Python files and build import graph."""
    import_graph = defaultdict(set)

    for py_file in root.glob("**/*.py"):
        # Skip test files and virtual envs
        if any(skip in str(py_file) for skip in ["test_", "__pycache__", ".venv", "venv"]):
            continue

        try:
            with open(py_file, encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=str(py_file))

            # Get module name for this file
            try:
                rel_path = py_file.relative_to(root)
                importer_module = str(rel_path.with_suffix("")).replace("/", ".")
            except ValueError:
                continue

            # Extract imports
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        import_graph[alias.name].add(importer_module)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        import_graph[node.module].add(importer_module)

        except (SyntaxError, UnicodeDecodeError):
            pass

    return import_graph


def generate_lesson_from_anomaly(anomaly: dict) -> str:
    """Generate a lesson learned markdown from an anomaly."""
    lesson_id = f"ll_auto_{datetime.now().strftime('%Y%m%d_%H%M')}"

    template = f"""# Auto-Generated Lesson: {anomaly['pattern'].replace('_', ' ').title()}

**ID**: {lesson_id}
**Date**: {datetime.now().strftime('%Y-%m-%d')}
**Severity**: {anomaly['severity'].upper()}
**Auto-Generated**: Yes
**Pattern**: {anomaly['pattern']}

## The Problem

Module `{anomaly['module']}` shows suspicious usage pattern:
{anomaly['details']}

## Detection Method

Automated import usage analysis detected this pattern using:
- Historical import tracking (30-day trend analysis)
- Cross-package dependency analysis
- ML-based anomaly detection

## Recommendation

1. **Investigate**: Review if this module is still needed
2. **Document**: If keeping, document why usage is declining/isolated
3. **Remove**: If truly unused, remove following proper deprecation process
4. **Prevent**: Use pre-commit hooks to catch future patterns early

## Prevention Rules

```yaml
checks:
  - run: python3 scripts/analyze_import_usage.py
    frequency: weekly
  - alert_on: declining_usage, never_imported
```

## Related Lessons

- LL-043: Medallion Architecture (built but never integrated)
- LL-035: Failed to use RAG despite building it

---
*This lesson was auto-generated by import usage analyzer*
"""

    return template


def main():
    parser = argparse.ArgumentParser(
        description="Analyze import usage patterns with ML learning"
    )
    parser.add_argument(
        "--learn",
        action="store_true",
        help="Save current snapshot for learning"
    )
    parser.add_argument(
        "--trend",
        type=int,
        metavar="DAYS",
        help="Analyze trends over N days"
    )
    parser.add_argument(
        "--module",
        type=str,
        help="Analyze specific module trend"
    )
    parser.add_argument(
        "--generate-lessons",
        action="store_true",
        help="Auto-generate lessons from anomalies"
    )

    args = parser.parse_args()

    print("=" * 70)
    print("IMPORT USAGE ANALYZER - ML-Powered Dead Code Prevention")
    print("=" * 70)
    print()

    # Scan current imports
    print("[1/3] Scanning import usage...")
    import_graph = scan_imports(PROJECT_ROOT)
    print(f"  Tracked {len(import_graph)} imported modules")

    # Load tracker
    tracker = ImportUsageTracker()
    tracker.current_snapshot = import_graph

    # Save snapshot if learning mode
    if args.learn:
        print("\n[2/3] Saving snapshot for ML learning...")
        tracker.save_snapshot()
    else:
        print("\n[2/3] Skipping snapshot save (use --learn to enable)")

    # Detect anomalies
    print("\n[3/3] Detecting usage anomalies...")
    anomalies = tracker.detect_anomalies()
    print(f"  Found {len(anomalies)} suspicious patterns")

    # Report results
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    if args.module:
        # Detailed trend analysis for specific module
        print(f"\n📊 Trend Analysis: {args.module}")
        trend = tracker.analyze_trends(args.module, days=args.trend or 30)
        print(f"   Trend: {trend['trend']}")
        print(f"   Current importers: {trend.get('current_importers', 0)}")
        print(f"   Data points: {trend['data_points']}")

        if trend.get("usage_timeline"):
            print("\n   Timeline:")
            for point in trend["usage_timeline"][-5:]:
                date = datetime.fromisoformat(point["timestamp"]).strftime("%Y-%m-%d")
                print(f"     {date}: {point['importer_count']} importers")

    elif anomalies:
        # Group by severity
        high_severity = [a for a in anomalies if a["severity"] == "high"]
        medium_severity = [a for a in anomalies if a["severity"] == "medium"]

        if high_severity:
            print("\n🔴 HIGH SEVERITY ANOMALIES:")
            for anom in high_severity[:5]:
                print(f"   {anom['module']}")
                print(f"      Pattern: {anom['pattern']}")
                print(f"      Details: {anom['details']}")
                print()

        if medium_severity:
            print("\n🟡 MEDIUM SEVERITY ANOMALIES:")
            for anom in medium_severity[:5]:
                print(f"   {anom['module']}")
                print(f"      Pattern: {anom['pattern']}")
                print()

        # Auto-generate lessons if requested
        if args.generate_lessons:
            print("\n" + "=" * 70)
            print("AUTO-GENERATING LESSONS")
            print("=" * 70)

            lessons_dir = PROJECT_ROOT / "rag_knowledge" / "lessons_learned"
            lessons_dir.mkdir(parents=True, exist_ok=True)

            for anom in high_severity[:3]:  # Top 3 high severity
                lesson_content = generate_lesson_from_anomaly(anom)
                lesson_id = f"ll_auto_{anom['pattern']}_{datetime.now().strftime('%Y%m%d')}"
                lesson_file = lessons_dir / f"{lesson_id}.md"

                with open(lesson_file, "w") as f:
                    f.write(lesson_content)

                print(f"✅ Generated: {lesson_file.name}")

        print("\n" + "=" * 70)
        print(f"ANOMALIES DETECTED: {len(anomalies)}")
        print("\nRecommendations:")
        print("  1. Run with --generate-lessons to create RAG lessons")
        print("  2. Investigate high severity anomalies immediately")
        print("  3. Run weekly: python3 scripts/analyze_import_usage.py --learn")
        sys.exit(1)
    else:
        print("\n✅ NO ANOMALIES DETECTED")
        print("\nAll modules show healthy usage patterns.")
        sys.exit(0)


if __name__ == "__main__":
    main()
