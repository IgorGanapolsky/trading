#!/usr/bin/env python3
"""
Workflow Health Dashboard - Aggregates workflow health data for monitoring.

This script:
1. Reads latest scan results from data/workflow_health/
2. Queries GitHub API for recent workflow runs
3. Generates a health summary for monitoring

Usage:
    python scripts/workflow_health_dashboard.py [--json] [--update]
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path


def load_latest_scan():
    """Load the most recent proactive scan results."""
    scan_file = Path("data/workflow_health/latest_scan.json")
    if scan_file.exists():
        with open(scan_file) as f:
            return json.load(f)
    return None


def calculate_health_score(scan_data: dict | None) -> tuple[int, str]:
    """Calculate overall health score (0-100) and status."""
    if not scan_data:
        return 50, "unknown"

    score = 100

    # Deduct points for issues
    if not scan_data.get("security_clean", True):
        security_issues = scan_data.get("security_issues", 0)
        score -= min(30, security_issues * 5)  # Up to 30 points for security

    if not scan_data.get("dead_code_clean", True):
        score -= 10  # 10 points for dead code

    if not scan_data.get("quality_good", True):
        score -= 10  # 10 points for quality issues

    # Determine status
    if score >= 90:
        status = "healthy"
    elif score >= 70:
        status = "warning"
    elif score >= 50:
        status = "degraded"
    else:
        status = "critical"

    return max(0, score), status


def generate_dashboard():
    """Generate the health dashboard."""
    scan_data = load_latest_scan()
    score, status = calculate_health_score(scan_data)

    dashboard = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "health_score": score,
        "status": status,
        "scan_data": scan_data,
        "recommendations": [],
    }

    # Add recommendations based on issues
    if scan_data:
        if not scan_data.get("security_clean"):
            dashboard["recommendations"].append(
                "Review security scan results and fix high-severity issues"
            )
        if not scan_data.get("dead_code_clean"):
            dashboard["recommendations"].append(
                "Remove dead code identified by vulture"
            )
        if not scan_data.get("quality_good"):
            dashboard["recommendations"].append(
                "Refactor complex functions with high cyclomatic complexity"
            )

    if not dashboard["recommendations"]:
        dashboard["recommendations"].append("No action needed - system healthy")

    return dashboard


def print_dashboard(dashboard: dict, as_json: bool = False):
    """Print the dashboard in a readable format."""
    if as_json:
        print(json.dumps(dashboard, indent=2))
        return

    print("=" * 60)
    print("🏥 WORKFLOW HEALTH DASHBOARD")
    print("=" * 60)
    print()

    # Health score with emoji
    score = dashboard["health_score"]
    status = dashboard["status"]
    emoji = {"healthy": "✅", "warning": "⚠️", "degraded": "🟡", "critical": "🔴"}.get(
        status, "❓"
    )

    print(f"Health Score: {score}/100 {emoji} ({status.upper()})")
    print(f"Generated: {dashboard['generated_at']}")
    print()

    # Scan details
    scan = dashboard.get("scan_data")
    if scan:
        print("📊 Latest Scan Results:")
        print(f"  - Security: {'✅ Clean' if scan.get('security_clean') else '❌ Issues'}")
        print(
            f"  - Dead Code: {'✅ Clean' if scan.get('dead_code_clean') else '⚠️ Found'}"
        )
        print(
            f"  - Code Quality: {'✅ Good' if scan.get('quality_good') else '⚠️ Issues'}"
        )
        print(f"  - Scan Time: {scan.get('timestamp', 'Unknown')}")
    else:
        print("📊 No scan data available yet")

    print()
    print("💡 Recommendations:")
    for rec in dashboard["recommendations"]:
        print(f"  • {rec}")

    print()
    print("=" * 60)


def update_dashboard_file(dashboard: dict):
    """Save the dashboard to a file."""
    output_dir = Path("data/workflow_health")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "dashboard.json"
    with open(output_file, "w") as f:
        json.dump(dashboard, f, indent=2)

    print(f"Dashboard saved to {output_file}")


def main():
    """Main entry point."""
    as_json = "--json" in sys.argv
    update = "--update" in sys.argv

    dashboard = generate_dashboard()

    if update:
        update_dashboard_file(dashboard)

    print_dashboard(dashboard, as_json=as_json)

    # Exit with non-zero if unhealthy
    if dashboard["status"] in ["critical", "degraded"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
