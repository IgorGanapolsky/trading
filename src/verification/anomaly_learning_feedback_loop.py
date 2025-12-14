"""Continuous Anomaly Pattern Learning Loop.

Automatically learns from every anomaly and updates prevention strategies in RAG.
Self-improving system that gets smarter with each detected issue.

Key Features:
1. Detects recurring anomaly patterns
2. Auto-ingests new lessons into RAG
3. Escalates severity based on recurrence
4. Creates GitHub issues for critical patterns
5. Generates daily anomaly reports

Usage:
    loop = AnomalyLearningLoop()

    # Process anomaly from detector
    result = loop.process_anomaly({
        "anomaly_id": "ANO-20251211-AMT",
        "type": "order_amount",
        "level": "warning",
        "message": "Order amount exceeds threshold",
        "details": {...},
        "detected_at": "2025-12-11T10:00:00Z",
        "context": {...}
    })

    # Generate daily report
    report = loop.generate_daily_report()

Author: Trading System
Created: 2025-12-11
"""

import json
import logging
import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.rag.lessons_learned_rag import LessonsLearnedRAG

logger = logging.getLogger(__name__)

# Recurrence tracking file
RECURRENCE_DB_PATH = Path("data/anomaly_recurrence.json")
DAILY_REPORT_PATH = Path("reports/anomaly_reports")


@dataclass
class RecurrenceRecord:
    """Tracks how many times an anomaly pattern has occurred."""

    pattern_id: str
    anomaly_type: str
    first_seen: str
    last_seen: str
    count: int
    severity: str
    lesson_id: Optional[str] = None
    github_issue: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "pattern_id": self.pattern_id,
            "anomaly_type": self.anomaly_type,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "count": self.count,
            "severity": self.severity,
            "lesson_id": self.lesson_id,
            "github_issue": self.github_issue,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RecurrenceRecord":
        return cls(
            pattern_id=data["pattern_id"],
            anomaly_type=data["anomaly_type"],
            first_seen=data["first_seen"],
            last_seen=data["last_seen"],
            count=data["count"],
            severity=data["severity"],
            lesson_id=data.get("lesson_id"),
            github_issue=data.get("github_issue"),
        )


class AnomalyLearningLoop:
    """
    Continuous learning loop that improves from every anomaly.

    The system:
    1. Detects when anomalies recur
    2. Auto-creates lessons for new patterns
    3. Escalates severity based on frequency
    4. Creates GitHub issues for critical issues
    5. Generates daily aggregation reports

    Severity Escalation:
    - 1-2 occurrences: LOW
    - 3-4 occurrences: MEDIUM
    - 5-6 occurrences: HIGH
    - 7+ occurrences: CRITICAL (auto-create GitHub issue)
    """

    def __init__(
        self,
        rag: Optional[LessonsLearnedRAG] = None,
        similarity_threshold: float = 0.7,
    ):
        """
        Initialize the learning loop.

        Args:
            rag: LessonsLearnedRAG instance (creates one if not provided)
            similarity_threshold: Threshold for considering lessons similar
        """
        self.rag = rag or LessonsLearnedRAG()
        self.similarity_threshold = similarity_threshold
        self.recurrence_records: dict[str, RecurrenceRecord] = {}
        self.daily_anomalies: list[dict] = []

        # Load recurrence history
        self._load_recurrence_db()

    def process_anomaly(self, anomaly: dict) -> dict:
        """
        Process a detected anomaly and learn from it.

        Args:
            anomaly: Anomaly dict with keys: anomaly_id, type, level, message,
                    details, detected_at, context

        Returns:
            Processing result dict with:
            - anomaly_processed: bool
            - is_recurring: bool
            - recurrence_count: int
            - severity: str
            - lesson_id: str (if new lesson created)
            - prevention_suggested: str
        """
        logger.info(f"Processing anomaly: {anomaly['anomaly_id']}")

        # Add to daily tracking
        self.daily_anomalies.append(anomaly)

        # Check if this is a recurring pattern
        recurrence = self.check_if_recurring(anomaly["type"])

        # Determine severity based on recurrence
        new_severity = self._escalate_severity(anomaly["type"], recurrence["recurrence_count"] + 1)

        # Update or create recurrence record
        self._update_recurrence(anomaly, new_severity)

        # Auto-ingest lesson if needed
        lesson_id = None
        prevention = None

        if recurrence["recurrence_count"] == 0:
            # New pattern - create lesson
            lesson_id = self.auto_ingest_lesson(anomaly)
            prevention = self._generate_prevention(anomaly)
            logger.info(f"Created new lesson: {lesson_id}")
        else:
            # Recurring pattern - update existing lesson if needed
            if recurrence["recurrence_count"] >= 3:
                # Update severity in RAG if escalated
                logger.info(
                    f"Recurring anomaly: {anomaly['type']} "
                    f"(count: {recurrence['recurrence_count'] + 1})"
                )
            prevention = self._generate_prevention(anomaly)

        # Create GitHub issue for critical patterns
        github_issue = None
        if new_severity == "CRITICAL":
            github_issue = self._create_github_issue(anomaly, recurrence["recurrence_count"] + 1)

        result = {
            "anomaly_processed": True,
            "is_recurring": recurrence["is_recurring"],
            "recurrence_count": recurrence["recurrence_count"] + 1,
            "severity": new_severity,
            "lesson_id": lesson_id,
            "prevention_suggested": prevention,
            "github_issue": github_issue,
        }

        # Save updated recurrence DB
        self._save_recurrence_db()

        return result

    def check_if_recurring(self, anomaly_type: str) -> dict:
        """
        Check if an anomaly type has occurred before.

        Args:
            anomaly_type: Type of anomaly (e.g., "order_amount", "data_staleness")

        Returns:
            Dict with:
            - is_recurring: bool
            - recurrence_count: int (0 if new)
            - last_seen: str (timestamp of last occurrence)
            - severity: str (current severity level)
        """
        pattern_id = self._get_pattern_id(anomaly_type)

        if pattern_id in self.recurrence_records:
            record = self.recurrence_records[pattern_id]
            return {
                "is_recurring": True,
                "recurrence_count": record.count,
                "last_seen": record.last_seen,
                "severity": record.severity,
            }

        return {
            "is_recurring": False,
            "recurrence_count": 0,
            "last_seen": None,
            "severity": "LOW",
        }

    def auto_ingest_lesson(self, anomaly: dict) -> str:
        """
        Automatically create a lesson from an anomaly.

        Args:
            anomaly: Anomaly dict

        Returns:
            Lesson ID
        """
        # Generate lesson content
        title = f"Anomaly: {anomaly['type']} - {anomaly['message']}"
        description = self._format_lesson_description(anomaly)
        root_cause = self._infer_root_cause(anomaly)
        prevention = self._generate_prevention(anomaly)

        # Determine severity
        severity = anomaly.get("level", "medium")
        if severity == "block":
            severity = "critical"
        elif severity == "warning":
            severity = "medium"
        elif severity == "info":
            severity = "low"

        # Extract financial impact if available
        financial_impact = anomaly.get("details", {}).get("financial_impact")
        symbol = anomaly.get("context", {}).get("symbol")

        # Add to RAG
        lesson_id = self.rag.add_lesson(
            category=anomaly["type"],
            title=title,
            description=description,
            root_cause=root_cause,
            prevention=prevention,
            tags=[
                "anomaly",
                anomaly["type"],
                "auto_generated",
                f"detected_{datetime.now().strftime('%Y%m%d')}",
            ],
            severity=severity,
            financial_impact=financial_impact,
            symbol=symbol,
        )

        # Update recurrence record with lesson ID
        pattern_id = self._get_pattern_id(anomaly["type"])
        if pattern_id in self.recurrence_records:
            self.recurrence_records[pattern_id].lesson_id = lesson_id

        logger.info(f"Auto-ingested lesson: {lesson_id} for anomaly type: {anomaly['type']}")
        return lesson_id

    def escalate_severity(self, anomaly_type: str, count: int) -> str:
        """
        Determine severity level based on recurrence count.

        Args:
            anomaly_type: Type of anomaly
            count: Number of occurrences

        Returns:
            Severity level: LOW, MEDIUM, HIGH, or CRITICAL
        """
        return self._escalate_severity(anomaly_type, count)

    def generate_daily_report(self) -> dict:
        """
        Generate daily aggregation report of all anomalies.

        Returns:
            Dict with:
            - date: str
            - total_anomalies: int
            - by_type: dict (anomaly type -> count)
            - by_severity: dict (severity -> count)
            - new_patterns: int
            - recurring_patterns: int
            - critical_issues: list
            - lessons_created: int
            - github_issues_created: int
        """
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")

        # Count anomalies by type and severity
        type_counts = Counter(a["type"] for a in self.daily_anomalies)
        severity_counts = Counter(a.get("level", "unknown") for a in self.daily_anomalies)

        # Identify new vs recurring patterns (count unique patterns, not occurrences)
        new_patterns = 0
        recurring_patterns = 0
        seen_patterns = set()

        for anomaly in self.daily_anomalies:
            pattern_id = self._get_pattern_id(anomaly["type"])

            # Only count each pattern once
            if pattern_id not in seen_patterns:
                seen_patterns.add(pattern_id)
                record = self.recurrence_records.get(pattern_id)
                if record and record.count == 1:
                    new_patterns += 1
                elif record and record.count > 1:
                    recurring_patterns += 1

        # Identify critical issues
        critical_issues = [
            {
                "anomaly_id": a["anomaly_id"],
                "type": a["type"],
                "message": a["message"],
                "count": self.recurrence_records.get(
                    self._get_pattern_id(a["type"]), RecurrenceRecord("", "", "", "", 0, "")
                ).count,
            }
            for a in self.daily_anomalies
            if a.get("level") == "critical" or a.get("level") == "block"
        ]

        # Count lessons and GitHub issues created today
        lessons_created = sum(
            1
            for r in self.recurrence_records.values()
            if r.lesson_id and r.last_seen.startswith(date_str)
        )

        github_issues = sum(
            1
            for r in self.recurrence_records.values()
            if r.github_issue and r.last_seen.startswith(date_str)
        )

        report = {
            "date": date_str,
            "total_anomalies": len(self.daily_anomalies),
            "by_type": dict(type_counts),
            "by_severity": dict(severity_counts),
            "new_patterns": new_patterns,
            "recurring_patterns": recurring_patterns,
            "critical_issues": critical_issues,
            "lessons_created": lessons_created,
            "github_issues_created": github_issues,
        }

        # Save report
        self._save_daily_report(report)

        # Reset daily tracking
        self.daily_anomalies = []

        logger.info(f"Generated daily anomaly report: {date_str}")
        return report

    # ========== Private Methods ==========

    def _get_pattern_id(self, anomaly_type: str) -> str:
        """Generate pattern ID from anomaly type."""
        return f"pattern_{anomaly_type}"

    def _escalate_severity(self, anomaly_type: str, count: int) -> str:
        """
        Escalate severity based on recurrence count.

        Severity Levels:
        - 1-2 occurrences: LOW
        - 3-4 occurrences: MEDIUM
        - 5-6 occurrences: HIGH
        - 7+ occurrences: CRITICAL
        """
        if count >= 7:
            return "CRITICAL"
        elif count >= 5:
            return "HIGH"
        elif count >= 3:
            return "MEDIUM"
        else:
            return "LOW"

    def _update_recurrence(self, anomaly: dict, severity: str) -> None:
        """Update or create recurrence record."""
        pattern_id = self._get_pattern_id(anomaly["type"])
        now = datetime.now(timezone.utc).isoformat()

        if pattern_id in self.recurrence_records:
            # Update existing record
            record = self.recurrence_records[pattern_id]
            record.count += 1
            record.last_seen = now
            record.severity = severity
        else:
            # Create new record
            self.recurrence_records[pattern_id] = RecurrenceRecord(
                pattern_id=pattern_id,
                anomaly_type=anomaly["type"],
                first_seen=now,
                last_seen=now,
                count=1,
                severity=severity,
            )

    def _format_lesson_description(self, anomaly: dict) -> str:
        """Format anomaly details into lesson description."""
        details = anomaly.get("details", {})
        context = anomaly.get("context", {})

        description = f"{anomaly['message']}\n\n"
        description += "Details:\n"
        for key, value in details.items():
            description += f"- {key}: {value}\n"

        if context:
            description += "\nContext:\n"
            for key, value in context.items():
                description += f"- {key}: {value}\n"

        description += f"\nDetected at: {anomaly['detected_at']}\n"
        description += f"Anomaly ID: {anomaly['anomaly_id']}"

        return description

    def _infer_root_cause(self, anomaly: dict) -> str:
        """Infer root cause from anomaly type and details."""
        anomaly_type = anomaly["type"]

        # Common root causes by type
        root_causes = {
            "order_amount": "Order amount calculation error or unit conversion mistake",
            "order_frequency": "Trading frequency outside expected range",
            "price_deviation": "Market volatility or stale price data",
            "data_staleness": "Data pipeline delay or API failure",
            "execution_failure": "API error, insufficient funds, or market conditions",
            "symbol_unknown": "Invalid symbol or symbol not in approved list",
            "market_hours": "Trade attempted outside market hours",
            "position_size": "Position sizing calculation error or risk limit violation",
            "volatility_spike": "Unusual market conditions or news event",
        }

        base_cause = root_causes.get(anomaly_type, "Unknown root cause")

        # Add specific details if available
        details = anomaly.get("details", {})
        if "multiplier" in details:
            base_cause += f" (Amount was {details['multiplier']:.1f}x expected)"

        return base_cause

    def _generate_prevention(self, anomaly: dict) -> str:
        """Generate prevention strategy for anomaly."""
        anomaly_type = anomaly["type"]

        # Common prevention strategies by type
        strategies = {
            "order_amount": "Add pre-trade validation: assert order_amount <= expected_daily * 2.0",
            "order_frequency": "Implement trade frequency throttling and monitoring",
            "price_deviation": "Add price deviation check before order submission",
            "data_staleness": "Validate data timestamp < 5 minutes before trading",
            "execution_failure": "Implement retry logic with exponential backoff",
            "symbol_unknown": "Validate symbol against approved list before trading",
            "market_hours": "Check market hours before submitting orders",
            "position_size": "Enforce position sizing limits at execution layer",
            "volatility_spike": "Add volatility filter: skip trading when volatility > 3 std dev",
        }

        return strategies.get(anomaly_type, f"Add validation check to prevent: {anomaly_type}")

    def _create_github_issue(self, anomaly: dict, count: int) -> Optional[str]:
        """
        Create GitHub issue for critical recurring anomalies.

        Args:
            anomaly: Anomaly dict
            count: Recurrence count

        Returns:
            GitHub issue URL or None if creation failed
        """
        pattern_id = self._get_pattern_id(anomaly["type"])
        record = self.recurrence_records.get(pattern_id)

        # Skip if issue already created
        if record and record.github_issue:
            logger.info(f"GitHub issue already exists: {record.github_issue}")
            return record.github_issue

        try:
            title = f"🚨 CRITICAL: {anomaly['type']} occurred {count} times"

            body = f"""## Critical Anomaly Alert

**Type**: {anomaly["type"]}
**Severity**: CRITICAL
**Occurrences**: {count}
**First Detected**: {record.first_seen if record else "Unknown"}
**Last Detected**: {anomaly["detected_at"]}

### Description

{anomaly["message"]}

### Details

```json
{json.dumps(anomaly.get("details", {}), indent=2)}
```

### Context

```json
{json.dumps(anomaly.get("context", {}), indent=2)}
```

### Root Cause

{self._infer_root_cause(anomaly)}

### Prevention Strategy

{self._generate_prevention(anomaly)}

### Related Lesson

{record.lesson_id if record and record.lesson_id else "Not yet created"}

---

**Auto-generated by AnomalyLearningLoop**
**Anomaly ID**: {anomaly["anomaly_id"]}
"""

            # Create issue using gh CLI
            result = subprocess.run(
                [
                    "gh",
                    "issue",
                    "create",
                    "--title",
                    title,
                    "--body",
                    body,
                    "--label",
                    "bug,critical,anomaly,auto-generated",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                issue_url = result.stdout.strip()
                logger.info(f"Created GitHub issue: {issue_url}")

                # Update recurrence record
                if record:
                    record.github_issue = issue_url

                return issue_url
            else:
                logger.error(f"Failed to create GitHub issue: {result.stderr}")
                return None

        except Exception as e:
            logger.error(f"Error creating GitHub issue: {e}")
            return None

    def _save_daily_report(self, report: dict) -> None:
        """Save daily report to file."""
        DAILY_REPORT_PATH.mkdir(parents=True, exist_ok=True)

        report_file = DAILY_REPORT_PATH / f"anomaly_report_{report['date']}.json"

        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)

        logger.info(f"Saved daily report: {report_file}")

    def _load_recurrence_db(self) -> None:
        """Load recurrence records from disk."""
        if not RECURRENCE_DB_PATH.exists():
            logger.info("No recurrence database found, starting fresh")
            return

        try:
            with open(RECURRENCE_DB_PATH) as f:
                data = json.load(f)

            for pattern_id, record_dict in data.items():
                self.recurrence_records[pattern_id] = RecurrenceRecord.from_dict(record_dict)

            logger.info(f"Loaded {len(self.recurrence_records)} recurrence records")

        except Exception as e:
            logger.error(f"Failed to load recurrence database: {e}")

    def _save_recurrence_db(self) -> None:
        """Save recurrence records to disk."""
        RECURRENCE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        data = {
            pattern_id: record.to_dict() for pattern_id, record in self.recurrence_records.items()
        }

        with open(RECURRENCE_DB_PATH, "w") as f:
            json.dump(data, f, indent=2)


if __name__ == "__main__":
    """Demo the anomaly learning feedback loop."""
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("ANOMALY LEARNING FEEDBACK LOOP DEMO")
    print("=" * 80)

    # Initialize
    loop = AnomalyLearningLoop()

    # Simulate detecting an anomaly
    print("\n" + "=" * 80)
    print("SIMULATING ANOMALY DETECTION")
    print("=" * 80)

    anomaly = {
        "anomaly_id": f"ANO-{datetime.now().strftime('%Y%m%d%H%M%S')}-AMT",
        "type": "order_amount",
        "level": "warning",
        "message": "Order amount $150.00 exceeds threshold $100.00",
        "details": {
            "amount": 150.0,
            "max_amount": 100.0,
            "expected_daily": 10.0,
            "multiplier": 15.0,
        },
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "context": {
            "symbol": "SPY",
            "amount": 150.0,
            "action": "BUY",
        },
    }

    # Process anomaly
    result = loop.process_anomaly(anomaly)

    print("\n✅ Anomaly processed:")
    print(f"  - Is recurring: {result['is_recurring']}")
    print(f"  - Recurrence count: {result['recurrence_count']}")
    print(f"  - Severity: {result['severity']}")
    print(f"  - Lesson ID: {result['lesson_id']}")
    print(f"  - Prevention: {result['prevention_suggested']}")

    # Process same anomaly again (should detect recurrence)
    print("\n" + "=" * 80)
    print("SIMULATING RECURRING ANOMALY")
    print("=" * 80)

    anomaly2 = {
        **anomaly,
        "anomaly_id": f"ANO-{datetime.now().strftime('%Y%m%d%H%M%S')}-AMT2",
        "detected_at": datetime.now(timezone.utc).isoformat(),
    }

    result2 = loop.process_anomaly(anomaly2)

    print("\n✅ Recurring anomaly processed:")
    print(f"  - Is recurring: {result2['is_recurring']}")
    print(f"  - Recurrence count: {result2['recurrence_count']}")
    print(f"  - Severity: {result2['severity']}")

    # Generate daily report
    print("\n" + "=" * 80)
    print("GENERATING DAILY REPORT")
    print("=" * 80)

    report = loop.generate_daily_report()

    print("\n📊 Daily Report:")
    print(f"  - Date: {report['date']}")
    print(f"  - Total anomalies: {report['total_anomalies']}")
    print(f"  - New patterns: {report['new_patterns']}")
    print(f"  - Recurring patterns: {report['recurring_patterns']}")
    print(f"  - Lessons created: {report['lessons_created']}")
    print(f"  - By type: {report['by_type']}")
    print(f"  - By severity: {report['by_severity']}")
