#!/usr/bin/env python3
"""
Auto-Reflect: Autonomous Rule Generation from Feedback

This script is called by capture_feedback.sh after every feedback event.
It analyzes patterns and generates rules WITHOUT requiring human approval.

Safety: Only low-impact rules are auto-applied. High-impact rules are flagged.

Usage:
    python scripts/auto_reflect.py
    python scripts/auto_reflect.py --force  # Force reflection even with few feedbacks
"""

import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path


class AutoReflect:
    """Autonomous reflection engine."""

    def __init__(self):
        self.feedback_db = Path("data/feedback_memory.db")
        self.diary_dir = Path(os.path.expanduser("~/.claude/memory/diary"))
        self.claude_md = Path(".claude/CLAUDE.md")
        self.auto_rules_file = Path("data/feedback/auto_rules.md")

        # Thresholds
        self.MIN_FEEDBACKS = 3  # Minimum feedbacks to trigger reflection
        self.PATTERN_THRESHOLD = 2  # Minimum occurrences to detect pattern
        self.HIGH_CONFIDENCE = 0.8  # Auto-apply if confidence above this

    def run(self, force: bool = False) -> dict:
        """Run autonomous reflection."""
        result = {
            "timestamp": datetime.now().isoformat(),
            "actions": [],
            "new_rules": [],
            "flagged_rules": [],
        }

        # 1. Check if we have enough feedback
        feedback_count = self._count_recent_feedback()
        if feedback_count < self.MIN_FEEDBACKS and not force:
            result["actions"].append(
                f"Skipped: Only {feedback_count} feedbacks (need {self.MIN_FEEDBACKS})"
            )
            return result

        # 2. Analyze diary entries
        diary_patterns = self._analyze_diary()
        result["actions"].append(f"Analyzed {len(diary_patterns)} diary patterns")

        # 3. Analyze feedback patterns
        feedback_patterns = self._analyze_feedback()
        result["actions"].append(f"Analyzed {len(feedback_patterns)} feedback patterns")

        # 4. Generate rules from patterns
        all_patterns = diary_patterns + feedback_patterns
        for pattern in all_patterns:
            rule = self._pattern_to_rule(pattern)
            if rule:
                if rule["confidence"] >= self.HIGH_CONFIDENCE:
                    # Auto-apply high-confidence rules
                    self._apply_rule(rule)
                    result["new_rules"].append(rule)
                else:
                    # Flag lower-confidence rules for review
                    result["flagged_rules"].append(rule)

        # 5. Update auto_rules.md
        if result["new_rules"]:
            self._update_rules_file(result["new_rules"])
            result["actions"].append(f"Applied {len(result['new_rules'])} new rules")

        # 6. Mark processed
        self._mark_processed()
        result["actions"].append("Marked feedback as processed")

        return result

    def _count_recent_feedback(self) -> int:
        """Count feedback in last 24 hours."""
        if not self.feedback_db.exists():
            return 0

        conn = sqlite3.connect(str(self.feedback_db))
        cursor = conn.execute("""
            SELECT COUNT(*) FROM session_feedback
            WHERE timestamp > datetime('now', '-1 day')
              AND processed = 0
        """)
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def _analyze_diary(self) -> list:
        """Analyze diary entries for patterns."""
        patterns = []

        if not self.diary_dir.exists():
            return patterns

        # Look at last 7 days of diary entries
        cutoff = datetime.now() - timedelta(days=7)

        for diary_file in self.diary_dir.glob("*.md"):
            try:
                # Parse date from filename (e.g., 2025-12-27_feedback.md)
                date_str = diary_file.stem.split("_")[0]
                file_date = datetime.strptime(date_str, "%Y-%m-%d")

                if file_date < cutoff:
                    continue

                content = diary_file.read_text()

                # Look for explicit feedback sections
                if "## Negative Feedback" in content:
                    patterns.append(
                        {
                            "type": "negative_diary",
                            "source": str(diary_file),
                            "content": content,
                        }
                    )

                if "## Positive Feedback" in content:
                    patterns.append(
                        {
                            "type": "positive_diary",
                            "source": str(diary_file),
                            "content": content,
                        }
                    )

            except (ValueError, IndexError):
                continue

        return patterns

    def _analyze_feedback(self) -> list:
        """Analyze feedback database for patterns."""
        patterns = []

        if not self.feedback_db.exists():
            return patterns

        conn = sqlite3.connect(str(self.feedback_db))

        # Find repeated negative patterns
        cursor = conn.execute(
            """
            SELECT user_message, COUNT(*) as count
            FROM session_feedback
            WHERE feedback_type = 'negative'
              AND processed = 0
            GROUP BY user_message
            HAVING count >= ?
        """,
            (self.PATTERN_THRESHOLD,),
        )

        for row in cursor.fetchall():
            patterns.append(
                {
                    "type": "repeated_negative",
                    "message": row[0],
                    "count": row[1],
                }
            )

        # Find repeated positive patterns
        cursor = conn.execute(
            """
            SELECT user_message, COUNT(*) as count
            FROM session_feedback
            WHERE feedback_type = 'positive'
              AND processed = 0
            GROUP BY user_message
            HAVING count >= ?
        """,
            (self.PATTERN_THRESHOLD,),
        )

        for row in cursor.fetchall():
            patterns.append(
                {
                    "type": "repeated_positive",
                    "message": row[0],
                    "count": row[1],
                }
            )

        conn.close()
        return patterns

    def _pattern_to_rule(self, pattern: dict) -> dict | None:
        """Convert a pattern to a rule."""
        ptype = pattern.get("type", "")

        if ptype == "repeated_negative":
            message = pattern.get("message", "")
            count = pattern.get("count", 1)

            # Extract actionable rule from message
            rule_text = self._extract_rule_from_negative(message)
            if rule_text:
                return {
                    "text": rule_text,
                    "confidence": min(count / 5, 1.0),  # Max confidence at 5 occurrences
                    "source": f"Repeated negative feedback ({count}x)",
                    "type": "AVOID",
                }

        elif ptype == "repeated_positive":
            message = pattern.get("message", "")
            count = pattern.get("count", 1)

            rule_text = self._extract_rule_from_positive(message)
            if rule_text:
                return {
                    "text": rule_text,
                    "confidence": min(count / 5, 1.0),
                    "source": f"Repeated positive feedback ({count}x)",
                    "type": "CONTINUE",
                }

        elif ptype == "negative_diary":
            content = pattern.get("content", "")
            # Extract what went wrong from diary
            match = re.search(r"\*\*User said:\*\*\s*(.+?)(?:\n|$)", content)
            if match:
                return {
                    "text": f"Avoid behavior that led to: {match.group(1)[:100]}",
                    "confidence": 0.6,  # Diary entries get moderate confidence
                    "source": "Diary analysis",
                    "type": "AVOID",
                }

        return None

    def _extract_rule_from_negative(self, message: str) -> str | None:
        """Extract a rule from negative feedback message."""
        message_lower = message.lower()

        # Common patterns that indicate what to avoid
        if "wrong" in message_lower or "incorrect" in message_lower:
            return "Verify claims before presenting them as facts"
        if "slow" in message_lower:
            return "Prioritize speed when user indicates urgency"
        if "too long" in message_lower or "verbose" in message_lower:
            return "Keep responses concise unless detail is requested"
        if "didn't listen" in message_lower or "ignored" in message_lower:
            return "Pay close attention to explicit user instructions"
        if "lie" in message_lower or "false" in message_lower:
            return "Never make claims without verification"

        # Generic fallback
        if len(message) < 100:
            return f"Avoid: {message}"

        return None

    def _extract_rule_from_positive(self, message: str) -> str | None:
        """Extract a rule from positive feedback message."""
        message_lower = message.lower()

        if "honest" in message_lower or "truth" in message_lower:
            return "Continue providing honest, direct assessments"
        if "quick" in message_lower or "fast" in message_lower:
            return "Maintain quick response times"
        if "helpful" in message_lower:
            return "Continue proactive problem-solving approach"
        if "clear" in message_lower:
            return "Maintain clear, structured communication"

        return None

    def _apply_rule(self, rule: dict):
        """Apply a rule to CLAUDE.md (append to Session-Learned Rules)."""
        if not self.claude_md.exists():
            return

        content = self.claude_md.read_text()

        # Find the Session-Learned Rules section
        marker = "## Session-Learned Rules"
        if marker not in content:
            # Add the section if it doesn't exist
            content += f"\n\n{marker}\n"

        # Check if rule already exists
        if rule["text"] in content:
            return

        # Append the rule
        rule_line = f"- {rule['text']}"

        # Insert after the marker
        parts = content.split(marker)
        if len(parts) == 2:
            # Find the end of the section (next ## or end of file)
            section_content = parts[1]
            next_section = section_content.find("\n## ")

            if next_section != -1:
                # Insert before next section
                new_section = (
                    section_content[:next_section]
                    + rule_line
                    + "\n"
                    + section_content[next_section:]
                )
            else:
                # Append to end
                new_section = section_content.rstrip() + "\n" + rule_line + "\n"

            new_content = parts[0] + marker + new_section
            self.claude_md.write_text(new_content)

    def _update_rules_file(self, rules: list):
        """Update the auto_rules.md file."""
        self.auto_rules_file.parent.mkdir(parents=True, exist_ok=True)

        content = "# Auto-Generated Rules\n\n"
        content += f"Last updated: {datetime.now().isoformat()}\n\n"

        for rule in rules:
            content += f"- [{rule['type']}] {rule['text']} (confidence: {rule['confidence']:.0%})\n"
            content += f"  Source: {rule['source']}\n\n"

        self.auto_rules_file.write_text(content)

    def _mark_processed(self):
        """Mark feedback entries as processed."""
        if not self.feedback_db.exists():
            return

        conn = sqlite3.connect(str(self.feedback_db))
        conn.execute("UPDATE session_feedback SET processed = 1 WHERE processed = 0")
        conn.commit()
        conn.close()


def main():
    force = "--force" in sys.argv

    reflector = AutoReflect()
    result = reflector.run(force=force)

    print(json.dumps(result, indent=2))

    # Exit with success
    return 0


if __name__ == "__main__":
    sys.exit(main())
