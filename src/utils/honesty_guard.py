"""
Honesty Guard - Prevents misleading metrics and false claims.

This module provides guards to ensure all reported metrics are honest and
verified. Created Dec 31, 2025 after discovering fake/hardcoded metrics.

MANDATE: Never lie. If a metric can't be calculated, report it as such.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

STATE_FILE = Path("data/system_state.json")
PERF_LOG_FILE = Path("data/performance_log.json")


class HonestyGuard:
    """
    Guards against misleading metrics and false claims.

    Validates that reported numbers match actual data sources.
    """

    def __init__(self):
        self.violations: list[dict] = []
        self.warnings: list[dict] = []

    def validate_win_rate(self) -> dict[str, Any]:
        """
        Validate that reported win_rate matches closed_trades data.

        Returns:
            Dict with validation result and any discrepancy details
        """
        if not STATE_FILE.exists():
            return {"valid": False, "error": "State file not found"}

        with open(STATE_FILE) as f:
            state = json.load(f)

        performance = state.get("performance", {})
        closed_trades = performance.get("closed_trades", [])
        reported_win_rate = performance.get("win_rate", 0.0)

        # Calculate actual
        winners = sum(1 for t in closed_trades if t.get("pl", 0) > 0)
        total = len(closed_trades)
        actual_win_rate = (winners / total * 100) if total > 0 else 0.0

        discrepancy = abs(actual_win_rate - reported_win_rate)
        is_valid = discrepancy < 1.0  # Allow 1% tolerance

        if not is_valid:
            self.violations.append({
                "type": "WIN_RATE_MISMATCH",
                "reported": reported_win_rate,
                "actual": actual_win_rate,
                "discrepancy": discrepancy,
                "timestamp": datetime.now().isoformat(),
            })

        return {
            "valid": is_valid,
            "reported": reported_win_rate,
            "actual": round(actual_win_rate, 2),
            "discrepancy": round(discrepancy, 2),
            "closed_trades_count": total,
        }

    def validate_pl_sanity(self) -> dict[str, Any]:
        """
        Validate that P/L numbers are sane and not stale.

        Returns:
            Dict with validation result
        """
        if not PERF_LOG_FILE.exists():
            return {"valid": False, "error": "Performance log not found"}

        with open(PERF_LOG_FILE) as f:
            perf_log = json.load(f)

        if not perf_log or not isinstance(perf_log, list):
            return {"valid": False, "error": "Empty performance log"}

        latest = perf_log[-1]
        latest_date = latest.get("date", "")

        # Check freshness
        try:
            log_date = datetime.fromisoformat(latest_date)
            days_stale = (datetime.now() - log_date).days
        except (ValueError, TypeError):
            days_stale = 999

        is_fresh = days_stale <= 3  # Allow 3 days (weekend + holiday)

        # Check for suspicious patterns
        suspicious = []

        # Same equity for multiple days
        if len(perf_log) >= 3:
            last_3_equities = [p.get("equity", 0) for p in perf_log[-3:]]
            if len(set(last_3_equities)) == 1 and last_3_equities[0] > 0:
                suspicious.append("Same equity for 3+ consecutive days")

        # Sudden large change (>10% in one day)
        if len(perf_log) >= 2:
            prev_equity = perf_log[-2].get("equity", 100000)
            curr_equity = latest.get("equity", 100000)
            if prev_equity > 0:
                daily_change = abs(curr_equity - prev_equity) / prev_equity
                if daily_change > 0.10:
                    suspicious.append(f"Large daily change: {daily_change*100:.1f}%")

        if suspicious:
            self.warnings.extend([
                {"type": "SUSPICIOUS_PATTERN", "detail": s, "timestamp": datetime.now().isoformat()}
                for s in suspicious
            ])

        return {
            "valid": is_fresh and not suspicious,
            "days_stale": days_stale,
            "is_fresh": is_fresh,
            "suspicious_patterns": suspicious,
            "latest_equity": latest.get("equity"),
            "latest_pl": latest.get("pl"),
        }

    def validate_metric(
        self,
        metric_name: str,
        value: Any,
        expected_range: Optional[tuple] = None,
        allow_none: bool = True,
    ) -> dict[str, Any]:
        """
        Validate a single metric value.

        Args:
            metric_name: Name of the metric
            value: The value to validate
            expected_range: Optional (min, max) tuple
            allow_none: Whether None is acceptable

        Returns:
            Validation result dict
        """
        if value is None:
            if allow_none:
                return {"valid": True, "metric": metric_name, "value": None, "note": "Not calculated"}
            else:
                self.violations.append({
                    "type": "NULL_METRIC",
                    "metric": metric_name,
                    "timestamp": datetime.now().isoformat(),
                })
                return {"valid": False, "metric": metric_name, "error": "Required metric is null"}

        if expected_range:
            min_val, max_val = expected_range
            if not (min_val <= value <= max_val):
                self.warnings.append({
                    "type": "OUT_OF_RANGE",
                    "metric": metric_name,
                    "value": value,
                    "expected_range": expected_range,
                    "timestamp": datetime.now().isoformat(),
                })
                return {
                    "valid": False,
                    "metric": metric_name,
                    "value": value,
                    "error": f"Value {value} outside expected range {expected_range}",
                }

        return {"valid": True, "metric": metric_name, "value": value}

    def run_all_validations(self) -> dict[str, Any]:
        """
        Run all honesty validations.

        Returns:
            Comprehensive validation report
        """
        self.violations = []
        self.warnings = []

        win_rate = self.validate_win_rate()
        pl_sanity = self.validate_pl_sanity()

        overall_valid = win_rate["valid"] and pl_sanity.get("valid", False)

        return {
            "overall_valid": overall_valid,
            "timestamp": datetime.now().isoformat(),
            "validations": {
                "win_rate": win_rate,
                "pl_sanity": pl_sanity,
            },
            "violations": self.violations,
            "warnings": self.warnings,
            "violation_count": len(self.violations),
            "warning_count": len(self.warnings),
        }

    def format_report(self) -> str:
        """Generate human-readable honesty report."""
        report = self.run_all_validations()

        lines = [
            "=" * 50,
            "HONESTY GUARD REPORT",
            "=" * 50,
            "",
            f"Timestamp: {report['timestamp']}",
            f"Overall Status: {'✅ PASS' if report['overall_valid'] else '❌ FAIL'}",
            "",
            "--- Win Rate Validation ---",
        ]

        wr = report["validations"]["win_rate"]
        if wr.get("error"):
            lines.append(f"  Error: {wr['error']}")
        else:
            lines.append(f"  Reported: {wr['reported']:.1f}%")
            lines.append(f"  Actual:   {wr['actual']:.1f}%")
            lines.append(f"  Valid:    {'✅' if wr['valid'] else '❌'}")

        lines.append("")
        lines.append("--- P/L Sanity Check ---")

        pl = report["validations"]["pl_sanity"]
        if pl.get("error"):
            lines.append(f"  Error: {pl['error']}")
        else:
            lines.append(f"  Days Stale: {pl['days_stale']}")
            lines.append(f"  Fresh:      {'✅' if pl['is_fresh'] else '❌'}")
            if pl["suspicious_patterns"]:
                lines.append("  Suspicious:")
                for p in pl["suspicious_patterns"]:
                    lines.append(f"    - {p}")

        if report["violations"]:
            lines.append("")
            lines.append("--- VIOLATIONS ---")
            for v in report["violations"]:
                lines.append(f"  ❌ {v['type']}: {v}")

        if report["warnings"]:
            lines.append("")
            lines.append("--- WARNINGS ---")
            for w in report["warnings"]:
                lines.append(f"  ⚠️ {w['type']}: {w.get('detail', w)}")

        lines.append("")
        lines.append("=" * 50)

        return "\n".join(lines)


def run_honesty_check() -> bool:
    """
    Run honesty check and return pass/fail.

    Returns:
        True if all validations pass, False otherwise
    """
    guard = HonestyGuard()
    report = guard.run_all_validations()

    if not report["overall_valid"]:
        logger.warning("Honesty check FAILED")
        print(guard.format_report())
        return False

    logger.info("Honesty check passed")
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    guard = HonestyGuard()
    print(guard.format_report())
