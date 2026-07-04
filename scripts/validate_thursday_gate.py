from datetime import datetime

from src.safety.constraint_engine import ConstraintEngine


def validate_constraint_engine():
    print(f"--- ConstraintEngine Validation: {datetime.now().strftime('%A, %Y-%m-%d')} ---")

    engine = ConstraintEngine()

    # Simulate trade metadata
    # Today is Friday (weekday 4). Thursday is 3.
    metadata = {"vix": 15.0, "width": 15.0, "weekday": datetime.now().weekday()}

    print(f"Testing validation for weekday: {metadata['weekday']}...")
    result = engine.validate_trade(
        symbol="SPY", position_size=200.0, current_positions=0, trades_today=0, metadata=metadata
    )

    print(f"Passed: {result.passed}")
    print(f"Violations: {result.violations}")

    if not result.passed and any("Weekday" in v for v in result.violations):
        print("\n✅ SUCCESS: ConstraintEngine correctly blocked a non-Thursday trade.")
    else:
        print("\n❌ FAILURE: ConstraintEngine failed to block the trade.")


if __name__ == "__main__":
    validate_constraint_engine()
