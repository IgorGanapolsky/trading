#!/usr/bin/env python3
"""
Log a new Ralph discovery for automatic blog publishing.

This script is used by Ralph to record significant discoveries during
autonomous iterations. Each logged discovery will be automatically
published to GitHub Pages and Dev.to.

Usage:
    python3 scripts/log_ralph_discovery.py \
        --title "Critical Security Fix: Missing Validation" \
        --category security \
        --severity critical \
        --summary "Found 4 scripts without ticker validation" \
        --problem "Scripts could execute trades on any ticker" \
        --solution "Added mandatory validate_ticker() calls" \
        --iteration 145

Categories: security, performance, bug_fix, data_integrity, architecture, testing, research
Severity: critical, high, medium, low
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

DISCOVERIES_FILE = Path(__file__).parent.parent / "data" / "ralph_discoveries.json"


def load_discoveries() -> dict:
    """Load existing discoveries."""
    if not DISCOVERIES_FILE.exists():
        return {
            "version": "1.0.0",
            "description": "Ralph Wiggum autonomous agent discoveries",
            "discoveries": []
        }
    with open(DISCOVERIES_FILE) as f:
        return json.load(f)


def save_discoveries(data: dict) -> None:
    """Save discoveries to file."""
    DISCOVERIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DISCOVERIES_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_next_id(discoveries: list) -> str:
    """Generate next discovery ID."""
    if not discoveries:
        return "RD-001"

    # Find highest existing ID
    max_num = 0
    for d in discoveries:
        id_str = d.get("id", "RD-000")
        try:
            num = int(id_str.split("-")[1])
            max_num = max(max_num, num)
        except (ValueError, IndexError):
            pass

    return f"RD-{max_num + 1:03d}"


def main():
    parser = argparse.ArgumentParser(
        description="Log a Ralph discovery for automatic blog publishing"
    )
    parser.add_argument("--title", required=True, help="Discovery title")
    parser.add_argument(
        "--category",
        required=True,
        choices=["security", "performance", "bug_fix", "data_integrity",
                 "architecture", "testing", "research"],
        help="Discovery category"
    )
    parser.add_argument(
        "--severity",
        required=True,
        choices=["critical", "high", "medium", "low"],
        help="Severity level"
    )
    parser.add_argument("--summary", required=True, help="Brief summary")
    parser.add_argument("--problem", help="Problem description")
    parser.add_argument("--root-cause", help="Root cause analysis")
    parser.add_argument("--impact", help="Potential impact")
    parser.add_argument("--solution", help="Solution implemented")
    parser.add_argument("--files", nargs="*", help="Files changed")
    parser.add_argument("--iteration", type=int, help="Ralph iteration number")
    parser.add_argument("--lessons", nargs="*", help="Lessons learned")
    parser.add_argument("--tests", type=int, help="Number of tests affected")

    args = parser.parse_args()

    # Load existing discoveries
    data = load_discoveries()
    discoveries = data.get("discoveries", [])

    # Create new discovery
    discovery_id = get_next_id(discoveries)
    discovery = {
        "id": discovery_id,
        "timestamp": datetime.now().isoformat(),
        "iteration": args.iteration or 0,
        "title": args.title,
        "category": args.category,
        "severity": args.severity,
        "summary": args.summary,
        "details": {
            "problem": args.problem or "",
            "root_cause": args.root_cause or "",
            "impact": args.impact or "",
            "solution": args.solution or "",
            "files_changed": args.files or [],
            "tests_affected": args.tests or 0,
            "tests_passing": True
        },
        "lessons_learned": args.lessons or [],
        "blog_published": False,
        "blog_urls": {}
    }

    # Add to discoveries
    discoveries.append(discovery)
    data["discoveries"] = discoveries

    # Save
    save_discoveries(data)

    print(f"✅ Discovery logged: {discovery_id}")
    print(f"   Title: {args.title}")
    print(f"   Category: {args.category}")
    print(f"   Severity: {args.severity}")
    print("\n📝 Blog post will be published automatically via GitHub Actions")
    print(f"   Or run: python3 scripts/generate_ralph_discovery_post.py --discovery {discovery_id}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
