"""Example usage of Pattern Recurrence Detector.

This script demonstrates how to use the PatternRecurrenceDetector to:
1. Detect recurring anomaly patterns
2. Analyze frequency and trends
3. Get prevention suggestions from RAG
4. Create GitHub issues for critical patterns

Usage:
    python3 examples/pattern_recurrence_example.py
"""

from src.verification.pattern_recurrence_detector import (
    PatternRecurrenceDetector,
    run_daily_pattern_analysis,
)


def example_basic_usage():
    """Basic pattern detection example."""
    print("=" * 60)
    print("EXAMPLE 1: Basic Pattern Detection")
    print("=" * 60)

    # Create detector
    detector = PatternRecurrenceDetector(
        recurrence_threshold=3,  # Flag patterns with 3+ occurrences
        window_days=7,  # Look back 7 days
        clustering_threshold_days=5,  # Flag patterns recurring every 5 days
    )

    # Analyze patterns
    report = detector.analyze_patterns()

    # Print summary
    print(f"\nTotal Anomalies: {report['total_anomalies']}")
    print(f"Unique Types: {report['unique_types']}")
    print(f"Recurring Patterns: {len(report['recurring_patterns'])}")
    print(f"Critical Patterns: {len(report['critical_patterns'])}")

    # Print each pattern
    for pattern in report["recurring_patterns"]:
        print(f"\nPattern: {pattern['pattern_type']}")
        print(f"  Count: {pattern['count']}")
        print(f"  Severity: {pattern['severity']}")
        print(f"  Frequency: Every {pattern['frequency_days']:.1f} days")
        print(f"  Trend: {pattern['trend']}")
        if pattern["prevention"]:
            print(f"  Prevention: {pattern['prevention']}")


def example_get_recurring_patterns():
    """Get recurring patterns as objects."""
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Get Recurring Patterns")
    print("=" * 60)

    detector = PatternRecurrenceDetector(window_days=30)
    patterns = detector.get_recurring_patterns()

    print(f"\nFound {len(patterns)} recurring patterns:\n")
    for pattern in patterns:
        print(f"  {pattern.pattern_type}:")
        print(f"    Severity: {pattern.severity}")
        print(f"    Count: {pattern.count}")
        print(f"    First seen: {pattern.first_seen}")
        print(f"    Last seen: {pattern.last_seen}")
        print()


def example_escalate_pattern():
    """Manually escalate a pattern's severity."""
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Escalate Pattern Severity")
    print("=" * 60)

    detector = PatternRecurrenceDetector(window_days=30)
    detector.analyze_patterns()

    # Find a pattern to escalate
    if detector.patterns:
        target = detector.patterns[0]
        print("\nBefore escalation:")
        print(f"  {target.pattern_type}: {target.severity}")

        # Escalate
        detector.escalate_pattern(target.pattern_type)

        # Check result
        for pattern in detector.patterns:
            if pattern.pattern_type == target.pattern_type:
                print("\nAfter escalation:")
                print(f"  {pattern.pattern_type}: {pattern.severity}")
                break


def example_create_github_issue():
    """Create GitHub issue for critical pattern."""
    print("\n" + "=" * 60)
    print("EXAMPLE 4: GitHub Issue Creation")
    print("=" * 60)

    detector = PatternRecurrenceDetector(window_days=30)
    detector.analyze_patterns()

    # Find critical patterns
    critical_patterns = [p for p in detector.patterns if p.severity == "CRITICAL"]

    if critical_patterns:
        print(f"\nFound {len(critical_patterns)} critical pattern(s)")
        for pattern in critical_patterns:
            print(f"\nPattern: {pattern.pattern_type}")
            print(f"  Count: {pattern.count}")
            print(f"  Frequency: Every {pattern.frequency_days:.1f} days")

            # Create GitHub issue (requires gh CLI)
            url = detector.create_github_issue(pattern)
            if url:
                print(f"  GitHub Issue: {url}")
            else:
                print("  (GitHub issue creation skipped - gh CLI not available)")
    else:
        print("\nNo critical patterns found (good!)")


def example_daily_cron_job():
    """Run as daily cron job."""
    print("\n" + "=" * 60)
    print("EXAMPLE 5: Daily Cron Job")
    print("=" * 60)

    print("\nRunning daily pattern analysis...")

    report = run_daily_pattern_analysis(
        recurrence_threshold=3,
        window_days=7,
        auto_create_issues=False,  # Set to True to auto-create issues
    )

    print("\nDaily Report:")
    print(f"  Total Anomalies: {report['total_anomalies']}")
    print(f"  Recurring Patterns: {len(report['recurring_patterns'])}")
    print(f"  Critical Patterns: {len(report['critical_patterns'])}")

    # Print critical patterns
    if report["critical_patterns"]:
        print("\n  CRITICAL PATTERNS REQUIRING ATTENTION:")
        for pattern in report["critical_patterns"]:
            print(f"    - {pattern['pattern_type']}: {pattern['count']} occurrences")


def example_clustering_detection():
    """Detect temporal clustering (patterns recurring every 2-5 days)."""
    print("\n" + "=" * 60)
    print("EXAMPLE 6: Temporal Clustering Detection")
    print("=" * 60)

    detector = PatternRecurrenceDetector(
        window_days=14,
        clustering_threshold_days=5,  # Flag if recurring every 5 days or less
    )

    report = detector.analyze_patterns()

    print("\nChecking for clustered patterns (recurring every 2-5 days):")
    for pattern in report["recurring_patterns"]:
        if 0 < pattern["frequency_days"] <= 5:
            print(f"\n  ⚠️  CLUSTERING DETECTED: {pattern['pattern_type']}")
            print(f"      Recurring every {pattern['frequency_days']:.1f} days")
            print(f"      Count: {pattern['count']}")
            print(f"      Severity: {pattern['severity']}")


if __name__ == "__main__":
    # Run all examples
    try:
        example_basic_usage()
        example_get_recurring_patterns()
        example_escalate_pattern()
        example_create_github_issue()
        example_daily_cron_job()
        example_clustering_detection()

        print("\n" + "=" * 60)
        print("Examples complete!")
        print("=" * 60)
        print("\nReport saved to: data/pattern_recurrence_report.json")
        print("\nCron job setup:")
        print(
            '  0 8 * * * cd /home/user/trading && python3 -c "from src.verification.pattern_recurrence_detector import run_daily_pattern_analysis; run_daily_pattern_analysis()"'
        )
        print()

    except Exception as e:
        print("\nNote: Examples may show warnings if anomaly log is empty")
        print(f"Error: {e}")
