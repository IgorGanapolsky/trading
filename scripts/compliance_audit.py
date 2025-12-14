#!/usr/bin/env python3
"""
Compliance Audit Scanner - Detect Gate Violations

Scans trade logs, state files, and telemetry for compliance violations:
- Kelly fraction limits
- Position concentration limits
- Daily loss limits
- Trading hours violations
- Circuit breaker bypasses

Run: python scripts/compliance_audit.py [--fix]

Author: Trading System CTO
Created: 2025-12-11
"""

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# Compliance thresholds
THRESHOLDS = {
    "max_kelly_fraction": 0.10,  # 10% max per position
    "max_position_concentration": 0.20,  # 20% max in single position
    "max_daily_loss_pct": 0.02,  # 2% max daily loss
    "trading_hours_start": 9.5,  # 9:30 AM ET
    "trading_hours_end": 16.0,  # 4:00 PM ET
    "max_consecutive_losses": 5,  # Trigger review after 5 consecutive losses
}


@dataclass
class Violation:
    """A compliance violation."""

    category: str
    severity: str  # low, medium, high, critical
    timestamp: str
    details: str
    file_source: str
    line_number: int | None = None
    recommended_action: str = ""


@dataclass
class AuditReport:
    """Complete audit report."""

    timestamp: str
    files_scanned: int
    violations: list[Violation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """Audit passes if no high/critical violations."""
        critical_count = sum(1 for v in self.violations if v.severity in ["high", "critical"])
        return critical_count == 0


class ComplianceAuditor:
    """Scan system for compliance violations."""

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or Path("data")
        self.violations: list[Violation] = []
        self.warnings: list[str] = []
        self.files_scanned = 0

    def scan_trade_logs(self) -> list[Violation]:
        """Scan trade logs for violations."""
        violations = []

        # Scan JSONL trade files
        for log_file in self.data_dir.glob("trades*.jsonl"):
            self.files_scanned += 1
            try:
                with open(log_file) as f:
                    for line_num, line in enumerate(f, 1):
                        trade = json.loads(line)
                        violations.extend(
                            self._check_trade_compliance(trade, str(log_file), line_num)
                        )
            except json.JSONDecodeError as e:
                self.warnings.append(f"Invalid JSON in {log_file}: {e}")
            except Exception as e:
                self.warnings.append(f"Error reading {log_file}: {e}")

        # Scan JSON trade files
        for log_file in self.data_dir.glob("trades*.json"):
            self.files_scanned += 1
            try:
                with open(log_file) as f:
                    data = json.load(f)
                    trades = data if isinstance(data, list) else [data]
                    for trade in trades:
                        violations.extend(self._check_trade_compliance(trade, str(log_file), None))
            except Exception as e:
                self.warnings.append(f"Error reading {log_file}: {e}")

        return violations

    def _check_trade_compliance(
        self, trade: dict[str, Any], file_source: str, line_num: int | None
    ) -> list[Violation]:
        """Check a single trade for compliance issues."""
        violations = []

        # Check Kelly fraction
        kelly = trade.get("kelly_fraction", 0)
        if kelly > THRESHOLDS["max_kelly_fraction"]:
            violations.append(
                Violation(
                    category="kelly_fraction",
                    severity="high",
                    timestamp=trade.get("timestamp", "unknown"),
                    details=f"Kelly fraction {kelly:.2%} exceeds {THRESHOLDS['max_kelly_fraction']:.2%} limit",
                    file_source=file_source,
                    line_number=line_num,
                    recommended_action="Reduce position size or review risk parameters",
                )
            )

        # Check trading hours
        ts = trade.get("timestamp")
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                hour = dt.hour + dt.minute / 60
                if (
                    hour < THRESHOLDS["trading_hours_start"]
                    or hour >= THRESHOLDS["trading_hours_end"]
                ):
                    violations.append(
                        Violation(
                            category="trading_hours",
                            severity="medium",
                            timestamp=ts,
                            details=f"Trade at {dt.strftime('%H:%M')} outside allowed hours (9:30 AM - 4:00 PM ET)",
                            file_source=file_source,
                            line_number=line_num,
                            recommended_action="Review after-hours trading settings",
                        )
                    )
            except ValueError:
                pass

        return violations

    def scan_system_state(self) -> list[Violation]:
        """Scan system state file for violations."""
        violations = []

        state_file = self.data_dir / "system_state.json"
        if not state_file.exists():
            self.warnings.append("system_state.json not found")
            return violations

        self.files_scanned += 1

        try:
            with open(state_file) as f:
                state = json.load(f)

            # Check position concentrations
            equity = state.get("account", {}).get("current_equity", 0)
            positions = state.get("performance", {}).get("open_positions", [])

            if equity > 0:
                for pos in positions:
                    pos_value = pos.get("market_value", 0) or (
                        pos.get("qty", 0) * pos.get("current_price", 0)
                    )
                    concentration = pos_value / equity if equity else 0

                    if concentration > THRESHOLDS["max_position_concentration"]:
                        violations.append(
                            Violation(
                                category="position_concentration",
                                severity="high",
                                timestamp=datetime.now().isoformat(),
                                details=f"Position {pos.get('ticker', 'unknown')} at {concentration:.1%} exceeds {THRESHOLDS['max_position_concentration']:.0%} limit",
                                file_source=str(state_file),
                                recommended_action="Reduce position size or rebalance portfolio",
                            )
                        )

            # Check daily loss
            daily_pnl = state.get("performance", {}).get("daily_pnl", 0)
            if equity > 0:
                daily_pnl_pct = daily_pnl / equity
                if daily_pnl_pct < -THRESHOLDS["max_daily_loss_pct"]:
                    violations.append(
                        Violation(
                            category="daily_loss",
                            severity="critical",
                            timestamp=datetime.now().isoformat(),
                            details=f"Daily loss {daily_pnl_pct:.2%} exceeds {THRESHOLDS['max_daily_loss_pct']:.0%} limit",
                            file_source=str(state_file),
                            recommended_action="Halt trading and review circuit breaker settings",
                        )
                    )

        except json.JSONDecodeError as e:
            self.warnings.append(f"Invalid JSON in system_state.json: {e}")
        except Exception as e:
            self.warnings.append(f"Error reading system_state.json: {e}")

        return violations

    def scan_telemetry(self) -> list[Violation]:
        """Scan telemetry logs for anomalies."""
        violations = []

        telemetry_dir = self.data_dir / "telemetry"
        if not telemetry_dir.exists():
            return violations

        for log_file in telemetry_dir.glob("*.jsonl"):
            self.files_scanned += 1
            try:
                with open(log_file) as f:
                    for line_num, line in enumerate(f, 1):
                        event = json.loads(line)

                        # Check for circuit breaker bypass attempts
                        if event.get("event_type") == "circuit_breaker_override":
                            violations.append(
                                Violation(
                                    category="circuit_breaker",
                                    severity="critical",
                                    timestamp=event.get("timestamp", "unknown"),
                                    details="Circuit breaker override detected",
                                    file_source=str(log_file),
                                    line_number=line_num,
                                    recommended_action="Investigate unauthorized override",
                                )
                            )

                        # Check for consecutive losses
                        if (
                            event.get("consecutive_losses", 0)
                            >= THRESHOLDS["max_consecutive_losses"]
                        ):
                            violations.append(
                                Violation(
                                    category="consecutive_losses",
                                    severity="medium",
                                    timestamp=event.get("timestamp", "unknown"),
                                    details=f"{event.get('consecutive_losses')} consecutive losses detected",
                                    file_source=str(log_file),
                                    line_number=line_num,
                                    recommended_action="Review strategy performance and consider pause",
                                )
                            )

            except Exception as e:
                self.warnings.append(f"Error reading {log_file}: {e}")

        return violations

    def scan_source_code(self) -> list[Violation]:
        """Scan source code for compliance issues."""
        violations = []

        src_dir = Path("src")
        if not src_dir.exists():
            return violations

        # Patterns that indicate potential issues
        dangerous_patterns = [
            (r"skip.*circuit.*breaker", "Circuit breaker bypass in code"),
            (r"disable.*risk", "Risk management disabled"),
            (r"force.*trade", "Forced trade execution"),
            (r"ignore.*limit", "Limit ignored"),
        ]

        for py_file in src_dir.rglob("*.py"):
            self.files_scanned += 1
            try:
                content = py_file.read_text()
                for pattern, description in dangerous_patterns:
                    matches = re.finditer(pattern, content, re.IGNORECASE)
                    for match in matches:
                        # Find line number
                        line_num = content[: match.start()].count("\n") + 1
                        violations.append(
                            Violation(
                                category="code_compliance",
                                severity="medium",
                                timestamp=datetime.now().isoformat(),
                                details=f"{description}: '{match.group()}'",
                                file_source=str(py_file),
                                line_number=line_num,
                                recommended_action="Review code for compliance",
                            )
                        )
            except Exception as e:
                self.warnings.append(f"Error reading {py_file}: {e}")

        return violations

    def run_full_audit(self) -> AuditReport:
        """Run complete compliance audit."""
        logger.info("Starting compliance audit...")

        # Run all scans
        self.violations.extend(self.scan_trade_logs())
        self.violations.extend(self.scan_system_state())
        self.violations.extend(self.scan_telemetry())
        self.violations.extend(self.scan_source_code())

        # Generate summary
        summary = {
            "total": len(self.violations),
            "critical": sum(1 for v in self.violations if v.severity == "critical"),
            "high": sum(1 for v in self.violations if v.severity == "high"),
            "medium": sum(1 for v in self.violations if v.severity == "medium"),
            "low": sum(1 for v in self.violations if v.severity == "low"),
        }

        report = AuditReport(
            timestamp=datetime.now().isoformat(),
            files_scanned=self.files_scanned,
            violations=self.violations,
            warnings=self.warnings,
            summary=summary,
        )

        logger.info(
            f"Audit complete: {self.files_scanned} files scanned, {len(self.violations)} violations found"
        )

        return report

    def save_report(self, report: AuditReport, output_path: Path | None = None):
        """Save audit report to file."""
        output_path = (
            output_path
            or self.data_dir
            / "audit_reports"
            / f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        report_dict = {
            "timestamp": report.timestamp,
            "files_scanned": report.files_scanned,
            "passed": report.passed,
            "summary": report.summary,
            "violations": [
                {
                    "category": v.category,
                    "severity": v.severity,
                    "timestamp": v.timestamp,
                    "details": v.details,
                    "file_source": v.file_source,
                    "line_number": v.line_number,
                    "recommended_action": v.recommended_action,
                }
                for v in report.violations
            ],
            "warnings": report.warnings,
        }

        with open(output_path, "w") as f:
            json.dump(report_dict, f, indent=2)

        logger.info(f"Report saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Run compliance audit")
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data",
        help="Data directory to scan",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file path for report",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Attempt to fix violations (not implemented)",
    )
    args = parser.parse_args()

    auditor = ComplianceAuditor(data_dir=Path(args.data_dir))
    report = auditor.run_full_audit()

    # Save report
    output_path = Path(args.output) if args.output else None
    auditor.save_report(report, output_path)

    # Print results
    print("\n" + "=" * 70)
    print("COMPLIANCE AUDIT REPORT")
    print("=" * 70)
    print(f"Timestamp:        {report.timestamp}")
    print(f"Files Scanned:    {report.files_scanned}")
    print(f"Status:           {'PASS' if report.passed else 'FAIL'}")
    print()
    print("SUMMARY:")
    print(f"  Critical:       {report.summary.get('critical', 0)}")
    print(f"  High:           {report.summary.get('high', 0)}")
    print(f"  Medium:         {report.summary.get('medium', 0)}")
    print(f"  Low:            {report.summary.get('low', 0)}")
    print(f"  Total:          {report.summary.get('total', 0)}")

    if report.violations:
        print("\nVIOLATIONS:")
        for v in report.violations:
            severity_icon = {"critical": "!!!", "high": "!!", "medium": "!", "low": "."}.get(
                v.severity, "?"
            )
            print(f"\n  [{severity_icon}] {v.category.upper()}: {v.details}")
            print(f"      Source: {v.file_source}" + (f":{v.line_number}" if v.line_number else ""))
            print(f"      Action: {v.recommended_action}")

    if report.warnings:
        print("\nWARNINGS:")
        for w in report.warnings:
            print(f"  - {w}")

    print("\n" + "=" * 70)

    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
