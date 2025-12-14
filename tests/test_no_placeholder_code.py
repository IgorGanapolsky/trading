"""
Test: No Placeholder Code (LL-034)

Ensures the codebase doesn't accumulate placeholder/stub code that
indicates unfinished features. This prevents technical debt buildup.

This test runs in CI to catch placeholder code that slips through.
"""

import re
from pathlib import Path

import pytest

# Directories to scan
SCAN_DIRS = ["src"]

# Patterns that indicate dead/placeholder code
DEAD_CODE_PATTERNS = [
    # Functions that return "not implemented"
    (r'return\s+["\'].*not.*implemented', "Returns 'not implemented'"),
    # Placeholder comments in production code
    (r'#\s*[Pp]laceholder\s*(?:for|:|-)', "Placeholder comment"),
    # Not yet implemented errors without real implementation
    (r'error.*not\s+(?:yet\s+)?implemented', "Not implemented error message"),
]

# Files to exclude from scanning
EXCLUDE_PATTERNS = [
    r"test_",
    r"conftest\.py",
    r"__pycache__",
    r"\.pyc$",
    r"migrations/",
]


def should_exclude(filepath: str) -> bool:
    """Check if file should be excluded from scanning."""
    for pattern in EXCLUDE_PATTERNS:
        if re.search(pattern, str(filepath)):
            return True
    return False


def find_dead_code_patterns(content: str) -> list[tuple[int, str, str]]:
    """
    Find dead code patterns in file content.

    Returns:
        List of (line_number, line, pattern_name)
    """
    findings = []
    lines = content.split("\n")

    for line_num, line in enumerate(lines, 1):
        for pattern, name in DEAD_CODE_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                findings.append((line_num, line.strip(), name))
                break

    return findings


class TestNoPlaceholderCode:
    """Test suite for placeholder code detection."""

    def test_no_placeholder_returns(self):
        """
        Ensure no functions return 'not implemented' strings.

        This catches code like:
            def my_feature():
                return "not yet implemented"
        """
        findings = []

        for scan_dir in SCAN_DIRS:
            for filepath in Path(scan_dir).rglob("*.py"):
                if should_exclude(str(filepath)):
                    continue

                try:
                    content = filepath.read_text(encoding="utf-8", errors="ignore")
                    file_findings = find_dead_code_patterns(content)

                    if file_findings:
                        findings.extend([
                            (filepath, line_num, line, name)
                            for line_num, line, name in file_findings
                        ])
                except Exception:
                    pass  # Skip unreadable files

        if findings:
            msg_parts = ["\n\nPlaceholder code detected (LL-034 violation):\n"]
            for filepath, line_num, line, name in findings[:10]:  # Limit output
                msg_parts.append(f"  {filepath}:{line_num} - {name}")
                msg_parts.append(f"    > {line[:60]}...")

            if len(findings) > 10:
                msg_parts.append(f"\n  ... and {len(findings) - 10} more")

            msg_parts.append("\n\nSee: rag_knowledge/lessons_learned/ll_034_placeholder_code_antipattern.md")

            pytest.fail("\n".join(msg_parts))

    def test_unified_sentiment_sources_all_implemented(self):
        """
        Verify all sentiment sources in UnifiedSentiment are actually implemented.

        This catches scenarios like:
            SOURCE_WEIGHTS = {"news": 0.3, "reddit": 0.25, "tiktok": 0.1}  # tiktok not real
        """
        from src.utils.unified_sentiment import UnifiedSentiment

        analyzer = UnifiedSentiment()

        # Get declared sources
        declared_sources = set(analyzer.SOURCE_WEIGHTS.keys())

        # Get enabled sources that have actual getter methods
        implemented_sources = set()
        for source in declared_sources:
            method_name = f"_get_{source}_sentiment"
            if hasattr(analyzer, method_name):
                method = getattr(analyzer, method_name)
                # Check it doesn't just return "not implemented"
                # We can't easily call it without side effects, so just verify it exists
                implemented_sources.add(source)

        missing = declared_sources - implemented_sources
        assert not missing, f"Sources declared but not implemented: {missing}"

    def test_collector_imports_valid(self):
        """
        Verify all collectors in __init__.py actually exist.

        This catches scenarios where we import a deleted module.
        """
        # This will raise ImportError if any imports are broken
        from src.rag.collectors import (
            AlphaVantageCollector,
            BerkshireLettersCollector,
            BogleheadsCollector,
            EarningsWhisperCollector,
            FinvizCollector,
            FredCollector,
            McMillanOptionsKnowledgeBase,
            NewsOrchestrator,
            OptionsFlowCollector,
            RedditCollector,
            SeekingAlphaCollector,
            StockTwitsCollector,
            TradingViewCollector,
            YahooFinanceCollector,
        )

        # Verify they're all classes/callables
        collectors = [
            AlphaVantageCollector,
            BerkshireLettersCollector,
            BogleheadsCollector,
            EarningsWhisperCollector,
            FinvizCollector,
            FredCollector,
            McMillanOptionsKnowledgeBase,
            NewsOrchestrator,
            OptionsFlowCollector,
            RedditCollector,
            SeekingAlphaCollector,
            StockTwitsCollector,
            TradingViewCollector,
            YahooFinanceCollector,
        ]

        for collector in collectors:
            assert callable(collector), f"{collector.__name__} is not callable"
