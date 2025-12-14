"""
Agent Configuration Verification Tests.

Tests that validate agent configuration files (CLAUDE.md, rules, etc.)
against best practices and prevent configuration drift.

Created: Dec 12, 2025
Lesson: ll_017 - CLAUDE.md bloat anti-pattern
"""

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent


class TestClaudeMdBestPractices:
    """Test CLAUDE.md follows Anthropic Dec 2025 best practices."""

    @pytest.fixture
    def claude_md_path(self) -> Path:
        return PROJECT_ROOT / ".claude" / "CLAUDE.md"

    @pytest.fixture
    def claude_md_content(self, claude_md_path: Path) -> str:
        if not claude_md_path.exists():
            pytest.skip("CLAUDE.md not found")
        return claude_md_path.read_text()

    def test_line_count_under_300(self, claude_md_content: str):
        """CLAUDE.md should be under 300 lines per Anthropic best practices."""
        lines = claude_md_content.split("\n")
        assert len(lines) <= 300, (
            f"CLAUDE.md has {len(lines)} lines, should be ≤300. "
            f"See rag_knowledge/lessons_learned/ll_017_claude_md_bloat_antipattern_dec12.md"
        )

    def test_character_count_under_10k(self, claude_md_content: str):
        """CLAUDE.md should be under 10k characters to save tokens."""
        char_count = len(claude_md_content)
        assert char_count <= 10000, (
            f"CLAUDE.md has {char_count} chars, should be ≤10k. "
            f"Move detailed content to .claude/rules/ or docs/"
        )

    def test_no_inline_code_blocks_over_10_lines(self, claude_md_content: str):
        """Code blocks should be short or moved to command files."""
        code_blocks = re.findall(r"```[\s\S]*?```", claude_md_content)

        for i, block in enumerate(code_blocks):
            lines = block.count("\n")
            assert lines <= 10, (
                f"Code block {i + 1} has {lines} lines. "
                f"Move to .claude/commands/ as a slash command."
            )

    def test_no_curl_commands_inline(self, claude_md_content: str):
        """API calls should be in command files, not CLAUDE.md."""
        has_curl = "curl -X" in claude_md_content or "curl -s" in claude_md_content

        assert not has_curl, (
            "CLAUDE.md contains curl commands. Move to .claude/commands/create-pr.md or similar."
        )

    def test_has_required_sections(self, claude_md_content: str):
        """CLAUDE.md should have key sections."""
        required_sections = [
            "Architecture",
            "Tech Stack",
            "Rules",
        ]

        for section in required_sections:
            assert section in claude_md_content, f"CLAUDE.md missing required section: {section}"

    def test_uses_pointers_not_copies(self, claude_md_content: str):
        """CLAUDE.md should point to docs, not copy them."""
        # Should reference docs/ directory
        has_doc_refs = "docs/" in claude_md_content

        assert has_doc_refs, "CLAUDE.md should reference docs/ for detailed documentation"

    def test_rules_in_separate_file(self):
        """Critical rules should be in .claude/rules/."""
        rules_dir = PROJECT_ROOT / ".claude" / "rules"
        assert rules_dir.exists(), ".claude/rules/ directory should exist for rule files"

        rules_files = list(rules_dir.glob("*.md"))
        assert len(rules_files) >= 1, "Should have at least one rules file in .claude/rules/"


class TestMandatoryRulesIntegrity:
    """Test mandatory rules file is properly structured."""

    @pytest.fixture
    def rules_path(self) -> Path:
        return PROJECT_ROOT / ".claude" / "rules" / "MANDATORY_RULES.md"

    @pytest.fixture
    def rules_content(self, rules_path: Path) -> str:
        if not rules_path.exists():
            pytest.skip("MANDATORY_RULES.md not found")
        return rules_path.read_text()

    def test_has_anti_lying_mandate(self, rules_content: str):
        """Anti-lying mandate must be present."""
        assert "lie" in rules_content.lower() and "never" in rules_content.lower(), (
            "Anti-lying mandate must be in MANDATORY_RULES.md"
        )

    def test_has_merge_rules(self, rules_content: str):
        """Merge-to-main prohibition must be present."""
        assert "merge" in rules_content.lower() and "main" in rules_content.lower(), (
            "Merge-to-main rules must be in MANDATORY_RULES.md"
        )

    def test_has_verification_hierarchy(self, rules_content: str):
        """Verification hierarchy must be documented."""
        assert "hook" in rules_content.lower() or "api" in rules_content.lower(), (
            "Data verification hierarchy must be in MANDATORY_RULES.md"
        )

    def test_rules_have_why_context(self, rules_content: str):
        """Rules should explain 'why' for Claude 4 models."""
        why_count = rules_content.lower().count("why")
        assert why_count >= 3, (
            f"Rules should have 'why' context (found {why_count}, need ≥3). "
            f"Claude 4 models perform better with motivation."
        )


class TestSlashCommandsExist:
    """Test slash commands are properly set up."""

    @pytest.fixture
    def commands_dir(self) -> Path:
        return PROJECT_ROOT / ".claude" / "commands"

    def test_commands_directory_exists(self, commands_dir: Path):
        """Commands directory should exist."""
        assert commands_dir.exists(), ".claude/commands/ should exist"

    def test_create_pr_command_exists(self, commands_dir: Path):
        """PR creation command should exist."""
        pr_command = commands_dir / "create-pr.md"
        assert pr_command.exists(), "create-pr.md should exist for PR creation procedure"


class TestRAGLessonsIntegration:
    """Test RAG lessons are properly indexed."""

    @pytest.fixture
    def lessons_dir(self) -> Path:
        return PROJECT_ROOT / "rag_knowledge" / "lessons_learned"

    def test_ll_017_exists(self, lessons_dir: Path):
        """ll_017 (CLAUDE.md bloat) lesson should exist."""
        ll_017 = lessons_dir / "ll_017_claude_md_bloat_antipattern_dec12.md"
        assert ll_017.exists(), "ll_017 lesson about CLAUDE.md bloat should exist"

    def test_lessons_have_actionable_fixes(self, lessons_dir: Path):
        """Lessons should have actionable prevention rules."""
        for lesson in lessons_dir.glob("*.md"):
            content = lesson.read_text()

            # Should have either Prevention, Fix, or Action section
            has_action = any(
                keyword in content for keyword in ["Prevention", "Fix", "Action", "Rule"]
            )

            assert has_action, f"{lesson.name} should have actionable prevention rules"


class TestTokenBudgetCompliance:
    """Test agent files stay within token budget."""

    def test_total_claude_config_under_5k_tokens(self):
        """Total .claude/ config should use <5% of context (~5k tokens)."""
        claude_dir = PROJECT_ROOT / ".claude"

        total_chars = 0
        for md_file in claude_dir.rglob("*.md"):
            # Skip cache and reports
            if "cache" in str(md_file) or "reports" in str(md_file):
                continue
            total_chars += len(md_file.read_text())

        # Rough estimate: 4 chars per token
        estimated_tokens = total_chars / 4

        assert estimated_tokens <= 5000, (
            f"Total .claude/ config uses ~{estimated_tokens:.0f} tokens, "
            f"should be ≤5000 to preserve context window"
        )


class TestProgressiveDisclosure:
    """Test progressive disclosure pattern is followed."""

    def test_claude_md_references_detailed_docs(self):
        """CLAUDE.md should reference detailed docs, not contain them."""
        claude_md = PROJECT_ROOT / ".claude" / "CLAUDE.md"
        if not claude_md.exists():
            pytest.skip("CLAUDE.md not found")

        content = claude_md.read_text()

        # Should have pointers to docs/
        doc_refs = content.count("docs/")
        assert doc_refs >= 2, (
            f"CLAUDE.md has {doc_refs} references to docs/, should have ≥2. "
            f"Use progressive disclosure: CLAUDE.md → docs/"
        )

    def test_detailed_docs_exist(self):
        """Referenced docs should actually exist."""
        docs_dir = PROJECT_ROOT / "docs"
        assert docs_dir.exists(), "docs/ directory should exist"

        required_docs = [
            "r-and-d-phase.md",
            "verification-protocols.md",
        ]

        for doc in required_docs:
            doc_path = docs_dir / doc
            assert doc_path.exists(), f"docs/{doc} should exist"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
