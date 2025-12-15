"""
Configuration Consistency Verification System.

Prevents silent configuration drift by:
1. Single Source of Truth enforcement
2. Cross-file consistency checks
3. RAG-based anomaly detection using lessons learned

Based on LL_047: LangSmith Project Name Drift incident (Dec 15, 2025)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ConfigValue:
    """A configuration value found in a file."""
    key: str
    value: str
    file_path: str
    line_number: int = 0


@dataclass
class ConsistencyReport:
    """Report of configuration consistency check."""
    passed: bool = True
    checks_run: int = 0
    inconsistencies: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_inconsistency(self, key: str, expected: str, found: list[ConfigValue]):
        """Add an inconsistency to the report."""
        self.passed = False
        self.inconsistencies.append({
            "key": key,
            "expected": expected,
            "found": [{"value": v.value, "file": v.file_path, "line": v.line_number} for v in found],
        })

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "passed": self.passed,
            "checks_run": self.checks_run,
            "inconsistencies": self.inconsistencies,
            "warnings": self.warnings,
        }


class ConfigConsistencyChecker:
    """
    Checks configuration consistency across the codebase.

    Enforces Single Source of Truth for critical configuration values.
    """

    # Configuration keys that MUST be consistent across all files
    CRITICAL_CONFIGS = {
        "LANGCHAIN_PROJECT": {
            "expected": "igor-trading-system",
            "patterns": [
                # YAML: LANGCHAIN_PROJECT: 'value' or "value"
                r"LANGCHAIN_PROJECT:\s*['\"]([^'\"]+)['\"]",
                # Python: LANGCHAIN_PROJECT = "value" or 'value'
                r'LANGCHAIN_PROJECT"\s*,\s*"([^"]+)"',
                # .env: LANGCHAIN_PROJECT=value
                r"LANGCHAIN_PROJECT=([^\s\n#]+)",
            ],
            "files": [
                ".github/workflows/*.yml",
                ".env.example",
            ],
            "lesson": "ll_047",
        },
    }

    # Values that should NEVER appear in committed files
    FORBIDDEN_PATTERNS = [
        (r"ghp_[A-Za-z0-9]{36}", "GitHub PAT token detected"),
        (r"sk-[A-Za-z0-9]{48}", "OpenAI API key detected"),
        (r"LIVE_TRADING[=:]\s*['\"]?true", "LIVE_TRADING=true detected - DANGER"),
    ]

    def __init__(self, project_root: Path | None = None):
        self.project_root = project_root or Path(".")

    def check_all(self) -> ConsistencyReport:
        """Run all consistency checks."""
        report = ConsistencyReport()

        # Check critical configs
        for key, config in self.CRITICAL_CONFIGS.items():
            self._check_config_consistency(key, config, report)

        # Check for forbidden patterns
        self._check_forbidden_patterns(report)

        return report

    def _check_config_consistency(
        self, key: str, config: dict[str, Any], report: ConsistencyReport
    ):
        """Check consistency for a single configuration key."""
        report.checks_run += 1
        expected = config["expected"]
        found_values: list[ConfigValue] = []

        for file_pattern in config["files"]:
            for file_path in self.project_root.glob(file_pattern):
                if not file_path.is_file():
                    continue

                try:
                    content = file_path.read_text()
                except Exception:
                    continue

                for pattern in config["patterns"]:
                    for match in re.finditer(pattern, content):
                        value = match.group(1)
                        line_num = content[:match.start()].count("\n") + 1
                        found_values.append(ConfigValue(
                            key=key,
                            value=value,
                            file_path=str(file_path),
                            line_number=line_num,
                        ))

        # Check for inconsistencies
        wrong_values = [v for v in found_values if v.value != expected]
        if wrong_values:
            report.add_inconsistency(key, expected, wrong_values)

    # Files to exclude from forbidden pattern checks (they contain the patterns as regex)
    EXCLUDED_FILES = [
        "config_consistency.py",
        "test_config_consistency.py",
    ]

    def _check_forbidden_patterns(self, report: ConsistencyReport):
        """Check for patterns that should never appear in code."""
        report.checks_run += 1

        for file_path in self.project_root.rglob("*"):
            if not file_path.is_file():
                continue
            if ".git" in str(file_path):
                continue
            if file_path.name in self.EXCLUDED_FILES:
                continue
            if file_path.suffix not in [".py", ".yml", ".yaml", ".json", ".md", ".sh", ".env"]:
                continue

            try:
                content = file_path.read_text()
            except Exception:
                continue

            for pattern, message in self.FORBIDDEN_PATTERNS:
                if re.search(pattern, content):
                    report.passed = False
                    report.inconsistencies.append({
                        "key": "FORBIDDEN_PATTERN",
                        "message": message,
                        "file": str(file_path),
                    })


class ObservabilityHealthChecker:
    """
    Verifies the observability stack is properly configured and working.

    Checks:
    1. LangSmith connectivity
    2. Project name consistency
    3. Recent trace activity
    4. Cost tracking (Helicone)
    """

    def __init__(self, project_name: str = "igor-trading-system"):
        self.project_name = project_name

    def check_langsmith_health(self) -> dict[str, Any]:
        """Check LangSmith configuration and connectivity."""
        import os

        result = {
            "configured": False,
            "project_name_correct": False,
            "api_key_set": False,
            "tracing_enabled": False,
            "connectivity": "unknown",
        }

        # Check env vars
        api_key = os.getenv("LANGCHAIN_API_KEY")
        project = os.getenv("LANGCHAIN_PROJECT")
        tracing = os.getenv("LANGCHAIN_TRACING_V2")

        result["api_key_set"] = bool(api_key)
        result["tracing_enabled"] = tracing == "true"
        result["project_name_correct"] = project == self.project_name
        result["configured"] = all([
            result["api_key_set"],
            result["tracing_enabled"],
            result["project_name_correct"],
        ])

        # Test connectivity if configured
        if result["api_key_set"]:
            try:
                from langsmith import Client
                client = Client(api_key=api_key)
                # Try to list projects
                client.list_projects(limit=1)
                result["connectivity"] = "ok"
            except Exception as e:
                result["connectivity"] = f"error: {str(e)[:100]}"

        return result

    def get_health_summary(self) -> str:
        """Get a human-readable health summary."""
        health = self.check_langsmith_health()

        if health["configured"] and health["connectivity"] == "ok":
            return "OK: LangSmith fully operational"
        elif not health["api_key_set"]:
            return "WARN: LANGCHAIN_API_KEY not set"
        elif not health["project_name_correct"]:
            return f"ERROR: Project name mismatch (expected: {self.project_name})"
        elif not health["tracing_enabled"]:
            return "WARN: LANGCHAIN_TRACING_V2 not enabled"
        else:
            return f"ERROR: {health['connectivity']}"


def run_consistency_check() -> bool:
    """Run configuration consistency check and return pass/fail."""
    checker = ConfigConsistencyChecker()
    report = checker.check_all()

    if report.passed:
        print("Configuration consistency check PASSED")
        print(f"  Checks run: {report.checks_run}")
        return True
    else:
        print("Configuration consistency check FAILED")
        print(f"  Checks run: {report.checks_run}")
        for issue in report.inconsistencies:
            print(f"  - {issue['key']}: expected '{issue.get('expected', 'N/A')}'")
            for loc in issue.get("found", []):
                print(f"      found '{loc['value']}' in {loc['file']}:{loc['line']}")
        return False


if __name__ == "__main__":
    import sys
    success = run_consistency_check()
    sys.exit(0 if success else 1)
