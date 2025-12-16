#!/usr/bin/env python3
"""
Fix lesson learned markdown files to have required fields.

Required format:
- **ID**: LL-XXX
- **Date**: YYYY-MM-DD
- **Severity**: CRITICAL/HIGH/MEDIUM/LOW
- **Category**: Category name
- **Impact**: Description of impact

And a ## Prevention Rules section
"""

import re
from pathlib import Path

LESSONS_DIR = Path("rag_knowledge/lessons_learned")


def extract_id_from_filename(filename: str) -> str:
    """Extract ID from filename like ll_010_dead_code.md -> LL-010."""
    match = re.search(r"ll_?(\d+)", filename.lower())
    if match:
        return f"LL-{match.group(1).zfill(3)}"

    # Special cases
    if "ci_failure" in filename:
        return "LL-CI-001"
    if "mandate" in filename:
        return "LL-MANDATE-001"
    if "autonomous" in filename:
        return "LL-AUTO-001"
    if "over_engineering" in filename:
        return "LL-OVERENG-001"
    if "one_thing" in filename:
        return "LL-ONE-001"

    return f"LL-{filename[:3].upper()}"


def fix_lesson_file(filepath: Path) -> bool:
    """Fix a lesson file to have required fields."""
    content = filepath.read_text()
    modified = False

    # Skip if already has **ID**
    if "**ID**" in content:
        return False

    # Get the filename for ID extraction
    lesson_id = extract_id_from_filename(filepath.stem)

    # Find the first heading
    lines = content.split("\n")
    insert_idx = 0

    for i, line in enumerate(lines):
        if line.startswith("# "):
            insert_idx = i + 1
            break
        # Skip YAML frontmatter
        if line == "---" and i == 0:
            for j in range(i + 1, len(lines)):
                if lines[j] == "---":
                    insert_idx = j + 1
                    # Also find the next heading
                    for k in range(j + 1, len(lines)):
                        if lines[k].startswith("# "):
                            insert_idx = k + 1
                            break
                    break
            break

    # Check what fields are missing
    has_id = "**ID**" in content
    has_impact = "**Impact**" in content
    has_prevention_rules = "Prevention Rules" in content or "Prevention Rule" in content

    # Build fields to add
    fields_to_add = []

    if not has_id:
        fields_to_add.append(f"**ID**: {lesson_id}")

    # Only add other fields if we're adding ID (don't mess with existing structure too much)
    if not has_impact and not has_id:
        # Try to extract impact from content
        impact = "Identified through automated analysis"
        if "impact" in content.lower():
            # Try to find an impact description
            impact_match = re.search(r"##\s*Impact\s*\n([^\n]+)", content, re.IGNORECASE)
            if impact_match:
                impact = impact_match.group(1).strip()[:80]
        fields_to_add.append(f"**Impact**: {impact}")

    if fields_to_add:
        # Find the right place to insert - after the title, before first empty line or section
        insert_content = "\n" + "\n".join(fields_to_add)

        # Insert after blank line following title
        for i in range(insert_idx, min(insert_idx + 5, len(lines))):
            if lines[i].strip() == "":
                lines.insert(i, insert_content)
                modified = True
                break
        else:
            # Just insert after title
            lines.insert(insert_idx, insert_content)
            modified = True

    # Add Prevention Rules section if missing (for CRITICAL lessons)
    if not has_prevention_rules and "CRITICAL" in content.upper():
        # Find Tags section or end of file
        tags_idx = None
        for i, line in enumerate(lines):
            if line.startswith("## Tags") or line.startswith("## Related"):
                tags_idx = i
                break

        prevention_section = "\n## Prevention Rules\n\n1. Apply lessons learned from this incident\n2. Add automated checks to prevent recurrence\n3. Update RAG knowledge base\n"

        if tags_idx:
            lines.insert(tags_idx, prevention_section)
        else:
            lines.append(prevention_section)
        modified = True

    if modified:
        filepath.write_text("\n".join(lines))
        print(f"Fixed: {filepath.name}")

    return modified


def main():
    """Fix all lesson files."""
    fixed_count = 0

    for lesson_file in LESSONS_DIR.glob("*.md"):
        if fix_lesson_file(lesson_file):
            fixed_count += 1

    print(f"\nFixed {fixed_count} lesson files")


if __name__ == "__main__":
    main()
