#!/usr/bin/env python3
"""
Skill Validation Script

Validates that skills with dependencies reference files that actually exist.
Prevents false promises in skill documentation.

Usage:
    python scripts/validate_skills.py
    python scripts/validate_skills.py --strict  # Fail on dormant skills

Exit codes:
    0: All active skills have valid dependencies
    1: Validation errors found
"""

import argparse
import re
import sys
from pathlib import Path

SKILLS_DIR = Path(".claude/skills")
PROJECT_ROOT = Path(".")


def parse_skill_frontmatter(skill_path: Path) -> dict:
    """Parse YAML frontmatter from skill file."""
    content = skill_path.read_text()

    # Extract frontmatter between --- markers
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}

    frontmatter = match.group(1)
    result = {
        "status": "unknown",
        "dependencies": [],
        "name": skill_path.parent.name,
    }

    for line in frontmatter.split("\n"):
        if line.strip().startswith("status:"):
            result["status"] = line.split(":", 1)[1].strip().split()[0]
        elif line.strip().startswith("name:"):
            result["name"] = line.split(":", 1)[1].strip()
        elif line.strip().startswith("- src/"):
            # Extract dependency path
            dep = line.strip().lstrip("- ").split("#")[0].strip()
            if "::" in dep:
                dep = dep.split("::")[0]
            result["dependencies"].append(dep)

    return result


def validate_skill(skill_path: Path, strict: bool = False) -> list[str]:
    """Validate a single skill. Returns list of errors."""
    errors = []
    info = parse_skill_frontmatter(skill_path)

    # Skip dormant skills unless strict mode
    if info.get("status") == "dormant":
        if strict:
            errors.append(f"DORMANT: {info['name']} is marked dormant")
        return errors

    # Check dependencies exist
    for dep in info.get("dependencies", []):
        dep_path = PROJECT_ROOT / dep
        if not dep_path.exists():
            errors.append(
                f"MISSING: {info.get('name', 'unknown')} depends on {dep} which does not exist"
            )

    return errors


def main():
    parser = argparse.ArgumentParser(description="Validate skill dependencies")
    parser.add_argument("--strict", action="store_true", help="Fail on dormant skills")
    args = parser.parse_args()

    if not SKILLS_DIR.exists():
        print("ERROR: .claude/skills directory not found")
        sys.exit(1)

    all_errors = []
    skills_checked = 0
    dormant_count = 0
    active_count = 0

    # Find all skill files
    for skill_file in SKILLS_DIR.rglob("*SKILL.md"):
        skills_checked += 1
        info = parse_skill_frontmatter(skill_file)

        if info.get("status") == "dormant":
            dormant_count += 1
        else:
            active_count += 1

        errors = validate_skill(skill_file, strict=args.strict)
        all_errors.extend(errors)

    # Also check lowercase skill.md
    for skill_file in SKILLS_DIR.rglob("*skill.md"):
        if "SKILL.md" not in str(skill_file):
            skills_checked += 1
            errors = validate_skill(skill_file, strict=args.strict)
            all_errors.extend(errors)

    # Report results
    print("\nSkill Validation Report")
    print("=" * 40)
    print(f"Skills checked: {skills_checked}")
    print(f"Active: {active_count}")
    print(f"Dormant: {dormant_count}")

    if all_errors:
        print(f"\nERRORS ({len(all_errors)}):")
        for error in all_errors:
            print(f"  - {error}")
        sys.exit(1)
    else:
        print("\n✅ All skill dependencies valid")
        sys.exit(0)


if __name__ == "__main__":
    main()
