"""
Example: Integrating Anomaly Learning Feedback Loop

This example shows how to integrate the AnomalyLearningLoop with the
TradingAnomalyDetector to create a self-improving trading system.

Author: Trading System
Created: 2025-12-11
"""

import logging
from datetime import datetime, timezone

from src.ml.anomaly_detector import TradingAnomalyDetector
from src.verification.anomaly_learning_feedback_loop import AnomalyLearningLoop

logging.basicConfig(level=logging.INFO)


def main():
    """Demonstrate anomaly detection + learning integration."""
    print("=" * 80)
    print("ANOMALY DETECTION + LEARNING INTEGRATION")
    print("=" * 80)

    # Initialize detector and learning loop
    detector = TradingAnomalyDetector(
        expected_daily_amount=10.0,
        portfolio_value=100000.0,
    )
    learning_loop = AnomalyLearningLoop()

    # Example 1: Validate a trade
    print("\n" + "=" * 80)
    print("EXAMPLE 1: Normal Trade")
    print("=" * 80)

    anomalies = detector.validate_trade(
        symbol="SPY",
        amount=10.0,
        action="BUY",
    )

    if anomalies:
        print(f"⚠️  {len(anomalies)} anomalies detected")
        for anomaly in anomalies:
            result = learning_loop.process_anomaly(anomaly.to_dict())
            print(f"  - {anomaly.message}")
            print(f"    Recurrence count: {result['recurrence_count']}")
            print(f"    Severity: {result['severity']}")
    else:
        print("✅ No anomalies detected - trade is safe")

    # Example 2: Oversized trade (triggers learning)
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Oversized Trade (200x error)")
    print("=" * 80)

    anomalies = detector.validate_trade(
        symbol="SPY",
        amount=2000.0,  # 200x expected amount!
        action="BUY",
    )

    if anomalies:
        print(f"🚨 {len(anomalies)} anomalies detected")
        for anomaly in anomalies:
            result = learning_loop.process_anomaly(anomaly.to_dict())
            print(f"  - {anomaly.message}")
            print(f"    Alert Level: {anomaly.alert_level.value}")
            print(f"    Recurrence: {result['recurrence_count']} times")
            print(f"    Severity: {result['severity']}")
            print(f"    Prevention: {result['prevention_suggested']}")

            # Check if trade should be blocked
            if anomaly.alert_level.value == "block":
                print(f"    ⛔ TRADE BLOCKED - too risky!")

    # Example 3: Simulate recurring pattern
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Recurring Pattern (triggers escalation)")
    print("=" * 80)

    # Simulate same error happening multiple times
    for i in range(5):
        anomalies = detector.validate_trade(
            symbol="SPY",
            amount=150.0,  # 15x expected
            action="BUY",
        )

        for anomaly in anomalies:
            result = learning_loop.process_anomaly(anomaly.to_dict())

            if i == 0:
                print(f"  Occurrence {i + 1}: Severity {result['severity']}")
            elif i == 2:
                print(f"  Occurrence {i + 1}: Severity {result['severity']} (escalated!)")
            elif i == 4:
                print(f"  Occurrence {i + 1}: Severity {result['severity']} (escalated!)")

    # Example 4: Daily report
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Daily Anomaly Report")
    print("=" * 80)

    report = learning_loop.generate_daily_report()

    print(f"📊 Daily Report for {report['date']}")
    print(f"  Total anomalies: {report['total_anomalies']}")
    print(f"  New patterns: {report['new_patterns']}")
    print(f"  Recurring patterns: {report['recurring_patterns']}")
    print(f"  Lessons created: {report['lessons_created']}")
    print(f"\n  By Type:")
    for anomaly_type, count in report['by_type'].items():
        print(f"    - {anomaly_type}: {count}")

    if report['critical_issues']:
        print(f"\n  🚨 Critical Issues:")
        for issue in report['critical_issues']:
            print(f"    - {issue['type']}: {issue['message']} (count: {issue['count']})")

    # Example 5: Query lessons learned
    print("\n" + "=" * 80)
    print("EXAMPLE 5: Query Lessons Learned")
    print("=" * 80)

    # Search for relevant lessons before trading
    results = learning_loop.rag.search(
        "large position size order amount",
        top_k=3
    )

    print("📚 Relevant lessons from past anomalies:")
    for lesson, score in results:
        print(f"\n  [{score:.2f}] {lesson.title}")
        print(f"  Category: {lesson.category}")
        print(f"  Severity: {lesson.severity}")
        print(f"  Prevention: {lesson.prevention}")

    print("\n" + "=" * 80)
    print("INTEGRATION COMPLETE")
    print("=" * 80)
    print("\nKey Benefits:")
    print("  ✅ Automatic learning from every anomaly")
    print("  ✅ Severity escalation for recurring issues")
    print("  ✅ Prevention strategies stored in RAG")
    print("  ✅ Daily aggregation and reporting")
    print("  ✅ Self-improving system over time")


if __name__ == "__main__":
    main()
