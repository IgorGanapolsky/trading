"""
Automatic Backtest Generation from Lessons Learned.

Generates backtest scenarios from lessons to validate that:
1. The fix for a lesson actually prevents the failure
2. New strategies don't repeat old mistakes
3. Edge cases from lessons are covered

Usage:
    from src.backtesting.lesson_to_backtest import LessonToBacktest

    generator = LessonToBacktest()

    # Generate backtests from all lessons
    scenarios = generator.generate_all_scenarios()

    # Run backtests
    results = generator.run_scenarios(scenarios)

Author: Trading System
Created: 2025-12-15
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

LESSONS_DIR = Path("rag_knowledge/lessons_learned")
BACKTEST_SCENARIOS_DIR = Path("data/backtest_scenarios")
BACKTEST_RESULTS_DIR = Path("reports/backtest_results")


@dataclass
class BacktestScenario:
    """A backtest scenario generated from a lesson."""

    lesson_id: str
    name: str
    description: str
    scenario_type: str  # "negative" (should fail) or "positive" (should pass)
    parameters: dict = field(default_factory=dict)
    expected_outcome: str = ""
    market_conditions: dict = field(default_factory=dict)
    date_range: tuple = field(default_factory=lambda: (None, None))

    def to_dict(self) -> dict:
        return {
            "lesson_id": self.lesson_id,
            "name": self.name,
            "description": self.description,
            "scenario_type": self.scenario_type,
            "parameters": self.parameters,
            "expected_outcome": self.expected_outcome,
            "market_conditions": self.market_conditions,
            "date_range": self.date_range,
        }


class LessonToBacktest:
    """
    Generate backtest scenarios from lessons learned.

    Parses lessons to extract:
    1. Market conditions that caused failures
    2. Symbols involved
    3. Strategy parameters
    4. Time periods
    5. Expected behaviors

    Then creates backtest scenarios to validate prevention measures.
    """

    # Keywords that indicate testable conditions
    CONDITION_KEYWORDS = {
        "volatility": ["volatility", "volatile", "vix", "spike"],
        "volume": ["volume", "liquidity", "thin"],
        "trend": ["trend", "momentum", "direction"],
        "time": ["market open", "market close", "overnight", "weekend"],
        "news": ["news", "earnings", "announcement", "event"],
        "correlation": ["correlation", "correlated", "sector"],
    }

    # Strategy name extraction patterns
    STRATEGY_PATTERNS = [
        r"(?:strategy|algo|system)[\s:]+(\w+)",
        r"(\w+)[\s]+strategy",
        r"(\w+)[\s]+trading",
    ]

    def __init__(
        self,
        lessons_dir: Optional[Path] = None,
        scenarios_dir: Optional[Path] = None,
    ):
        self.lessons_dir = lessons_dir or LESSONS_DIR
        self.scenarios_dir = scenarios_dir or BACKTEST_SCENARIOS_DIR
        self.scenarios_dir.mkdir(parents=True, exist_ok=True)

    def generate_all_scenarios(self) -> list[BacktestScenario]:
        """
        Generate backtest scenarios from all lessons.

        Returns:
            List of BacktestScenario objects
        """
        scenarios = []

        if not self.lessons_dir.exists():
            logger.warning(f"Lessons directory not found: {self.lessons_dir}")
            return scenarios

        for md_file in self.lessons_dir.glob("ll_*.md"):
            try:
                lesson_scenarios = self.generate_scenarios_from_lesson(md_file)
                scenarios.extend(lesson_scenarios)
            except Exception as e:
                logger.warning(f"Failed to generate scenarios from {md_file}: {e}")

        logger.info(f"Generated {len(scenarios)} backtest scenarios from lessons")
        return scenarios

    def generate_scenarios_from_lesson(self, lesson_path: Path) -> list[BacktestScenario]:
        """
        Generate backtest scenarios from a single lesson.

        Args:
            lesson_path: Path to lesson markdown file

        Returns:
            List of BacktestScenario objects
        """
        content = lesson_path.read_text()
        lesson_id = lesson_path.stem

        scenarios = []

        # Extract lesson metadata
        metadata = self._extract_metadata(content)
        severity = metadata.get("severity", "MEDIUM")

        # Only generate scenarios for HIGH and CRITICAL lessons
        if severity not in ["HIGH", "CRITICAL"]:
            return scenarios

        # Extract testable conditions
        conditions = self._extract_conditions(content)
        symbols = self._extract_symbols(content)
        strategies = self._extract_strategies(content)

        # Generate negative scenario (reproduces the failure conditions)
        if conditions or symbols:
            negative_scenario = BacktestScenario(
                lesson_id=lesson_id,
                name=f"Negative: {metadata.get('title', lesson_id)}",
                description=f"Reproduce failure conditions from {lesson_id}",
                scenario_type="negative",
                parameters={
                    "symbols": symbols or ["SPY"],
                    "strategies": strategies or ["default"],
                },
                expected_outcome="Trade should be blocked or flagged",
                market_conditions=conditions,
            )
            scenarios.append(negative_scenario)

        # Generate positive scenario (with prevention measures)
        if metadata.get("prevention_rules"):
            positive_scenario = BacktestScenario(
                lesson_id=lesson_id,
                name=f"Positive: {metadata.get('title', lesson_id)} (with fix)",
                description=f"Verify prevention measures from {lesson_id}",
                scenario_type="positive",
                parameters={
                    "symbols": symbols or ["SPY"],
                    "strategies": strategies or ["default"],
                    "prevention_enabled": True,
                },
                expected_outcome="Trade should succeed with prevention",
                market_conditions=conditions,
            )
            scenarios.append(positive_scenario)

        # Generate edge case scenarios
        edge_cases = self._generate_edge_cases(content, metadata)
        for edge_case in edge_cases:
            edge_scenario = BacktestScenario(
                lesson_id=lesson_id,
                name=f"Edge: {edge_case['name']}",
                description=edge_case["description"],
                scenario_type="edge",
                parameters=edge_case.get("parameters", {}),
                expected_outcome=edge_case.get("expected", "Should handle gracefully"),
                market_conditions=edge_case.get("conditions", {}),
            )
            scenarios.append(edge_scenario)

        return scenarios

    def save_scenarios(self, scenarios: list[BacktestScenario]) -> Path:
        """
        Save scenarios to JSON file.

        Args:
            scenarios: List of scenarios to save

        Returns:
            Path to saved file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = self.scenarios_dir / f"scenarios_{timestamp}.json"

        data = {
            "generated_at": datetime.now().isoformat(),
            "scenario_count": len(scenarios),
            "scenarios": [s.to_dict() for s in scenarios],
        }

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

        logger.info(f"Saved {len(scenarios)} scenarios to {output_path}")
        return output_path

    def generate_pytest_tests(self, scenarios: list[BacktestScenario]) -> str:
        """
        Generate pytest test code from scenarios.

        Args:
            scenarios: List of scenarios

        Returns:
            Python test code as string
        """
        test_code = '''"""
Auto-generated backtest tests from lessons learned.

Generated: {timestamp}
Scenarios: {count}

These tests validate that:
1. Known failure conditions are detected
2. Prevention measures work
3. Edge cases are handled

Run with: pytest tests/test_lesson_backtests.py -v
"""

import pytest
from datetime import datetime

# Import backtest framework
try:
    from src.backtesting.backtest_engine import BacktestEngine
    BACKTEST_AVAILABLE = True
except ImportError:
    BACKTEST_AVAILABLE = False


@pytest.fixture
def backtest_engine():
    """Initialize backtest engine."""
    if not BACKTEST_AVAILABLE:
        pytest.skip("Backtest engine not available")
    return BacktestEngine()


'''.format(
            timestamp=datetime.now().isoformat(),
            count=len(scenarios),
        )

        # Generate test for each scenario
        for i, scenario in enumerate(scenarios):
            test_name = self._sanitize_test_name(scenario.name)

            test_code += f'''
class Test{scenario.lesson_id.replace("-", "_").title()}:
    """Tests for {scenario.lesson_id}"""

    @pytest.mark.backtest
    def test_{test_name}_{i}(self, backtest_engine):
        """
        {scenario.description}

        Scenario Type: {scenario.scenario_type}
        Expected: {scenario.expected_outcome}
        """
        scenario = {{
            "name": "{scenario.name}",
            "lesson_id": "{scenario.lesson_id}",
            "type": "{scenario.scenario_type}",
            "parameters": {scenario.parameters},
            "market_conditions": {scenario.market_conditions},
        }}

        result = backtest_engine.run_scenario(scenario)

        # Validate based on scenario type
        if scenario["type"] == "negative":
            # Negative scenarios should be blocked or show loss
            assert result.get("blocked") or result.get("pnl", 0) < 0, \\
                f"Negative scenario should fail: {{result}}"
        elif scenario["type"] == "positive":
            # Positive scenarios should succeed
            assert not result.get("blocked"), \\
                f"Positive scenario should succeed: {{result}}"
        else:
            # Edge cases should not crash
            assert "error" not in result, \\
                f"Edge case should handle gracefully: {{result}}"

'''

        return test_code

    def save_pytest_tests(self, scenarios: list[BacktestScenario]) -> Path:
        """
        Save generated pytest tests to file.

        Args:
            scenarios: List of scenarios

        Returns:
            Path to test file
        """
        test_code = self.generate_pytest_tests(scenarios)
        test_path = Path("tests/test_lesson_backtests.py")

        test_path.write_text(test_code)
        logger.info(f"Generated pytest tests: {test_path}")

        return test_path

    def _extract_metadata(self, content: str) -> dict:
        """Extract metadata from lesson markdown."""
        metadata = {}

        # Title
        title_match = re.search(r"^# (.+)$", content, re.MULTILINE)
        if title_match:
            metadata["title"] = title_match.group(1).replace("Lesson Learned: ", "")

        # Severity
        severity_match = re.search(r"\*\*Severity\*\*:\s*(\w+)", content, re.IGNORECASE)
        if severity_match:
            metadata["severity"] = severity_match.group(1).upper()

        # Category
        category_match = re.search(r"\*\*Category\*\*:\s*(.+)$", content, re.MULTILINE)
        if category_match:
            metadata["category"] = category_match.group(1).strip()

        # Prevention rules
        prevention_rules = []
        in_prevention = False
        for line in content.split("\n"):
            if "## Prevention" in line:
                in_prevention = True
            elif line.startswith("##") and in_prevention:
                in_prevention = False
            elif in_prevention and line.strip().startswith("-"):
                prevention_rules.append(line.strip().lstrip("- "))

        metadata["prevention_rules"] = prevention_rules

        return metadata

    def _extract_conditions(self, content: str) -> dict:
        """Extract market conditions from lesson content."""
        conditions = {}
        content_lower = content.lower()

        for condition_type, keywords in self.CONDITION_KEYWORDS.items():
            for keyword in keywords:
                if keyword in content_lower:
                    # Try to extract value
                    pattern = rf"{keyword}\s*(?:of|at|around|>|<|=)?\s*([\d.]+%?)"
                    match = re.search(pattern, content_lower)
                    if match:
                        value = match.group(1)
                        conditions[condition_type] = value
                    else:
                        conditions[condition_type] = "elevated"
                    break

        return conditions

    def _extract_symbols(self, content: str) -> list:
        """Extract trading symbols from lesson content."""
        # Common stock symbols pattern
        symbols = re.findall(r'\b([A-Z]{1,5})\b', content)

        # Filter out common words
        common_words = {
            "THE", "AND", "FOR", "NOT", "BUT", "ARE", "WAS", "HAS", "HAD",
            "LOW", "HIGH", "BUY", "SELL", "API", "RAG", "ML", "CI", "CD",
        }

        # Known trading symbols
        known_symbols = {
            "SPY", "QQQ", "NVDA", "AAPL", "GOOGL", "MSFT", "AMZN", "META",
            "TSLA", "AMD", "INTC", "GLD", "SLV", "BTC", "ETH",
        }

        valid_symbols = [
            s for s in symbols
            if s not in common_words and (s in known_symbols or len(s) <= 4)
        ]

        return list(set(valid_symbols))[:5]  # Limit to 5

    def _extract_strategies(self, content: str) -> list:
        """Extract strategy names from lesson content."""
        strategies = []
        content_lower = content.lower()

        # Known strategies
        known_strategies = [
            "momentum", "mean_reversion", "breakout", "trend_following",
            "macd", "rsi", "bollinger", "scalping", "swing",
        ]

        for strategy in known_strategies:
            if strategy in content_lower:
                strategies.append(strategy)

        # Extract from patterns
        for pattern in self.STRATEGY_PATTERNS:
            matches = re.findall(pattern, content_lower)
            strategies.extend(matches)

        return list(set(strategies))[:3]  # Limit to 3

    def _generate_edge_cases(self, content: str, metadata: dict) -> list:
        """Generate edge case scenarios from lesson content."""
        edge_cases = []
        content_lower = content.lower()

        # Common edge cases based on content
        if "zero" in content_lower or "empty" in content_lower:
            edge_cases.append({
                "name": "Zero/empty values",
                "description": "Test with zero or empty values",
                "parameters": {"quantity": 0, "price": 0},
            })

        if "null" in content_lower or "none" in content_lower:
            edge_cases.append({
                "name": "Null handling",
                "description": "Test with null/None values",
                "parameters": {"symbol": None},
            })

        if "negative" in content_lower:
            edge_cases.append({
                "name": "Negative values",
                "description": "Test with negative values",
                "parameters": {"quantity": -1, "price": -100},
            })

        if "large" in content_lower or "exceed" in content_lower:
            edge_cases.append({
                "name": "Large values",
                "description": "Test with very large values",
                "parameters": {"quantity": 1000000, "price": 99999},
            })

        if "timeout" in content_lower or "slow" in content_lower:
            edge_cases.append({
                "name": "Timeout handling",
                "description": "Test timeout scenarios",
                "conditions": {"api_delay": 30},
            })

        return edge_cases

    def _sanitize_test_name(self, name: str) -> str:
        """Convert scenario name to valid Python identifier."""
        # Remove special characters, convert spaces to underscores
        sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", name.lower())
        # Remove consecutive underscores
        sanitized = re.sub(r"_+", "_", sanitized)
        # Remove leading/trailing underscores
        return sanitized.strip("_")[:50]


if __name__ == "__main__":
    """Demo backtest generation from lessons."""
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("LESSON-TO-BACKTEST GENERATOR DEMO")
    print("=" * 80)

    generator = LessonToBacktest()

    # Generate scenarios
    print("\n1. Generating scenarios from lessons...")
    scenarios = generator.generate_all_scenarios()
    print(f"   Generated {len(scenarios)} scenarios")

    # Show some scenarios
    print("\n2. Sample scenarios:")
    for scenario in scenarios[:5]:
        print(f"   - [{scenario.scenario_type}] {scenario.name}")
        print(f"     Lesson: {scenario.lesson_id}")
        print(f"     Expected: {scenario.expected_outcome}")
        print()

    # Save scenarios
    print("3. Saving scenarios...")
    scenarios_path = generator.save_scenarios(scenarios)
    print(f"   Saved to: {scenarios_path}")

    # Generate pytest tests
    print("\n4. Generating pytest tests...")
    test_path = generator.save_pytest_tests(scenarios)
    print(f"   Generated: {test_path}")

    print("\n" + "=" * 80)
    print("Run generated tests with:")
    print("  pytest tests/test_lesson_backtests.py -v --tb=short")
    print("=" * 80)
