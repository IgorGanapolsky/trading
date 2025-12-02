"""
Test Suite for Order Validation

Tests order size validation to prevent Mistake #1 ($1,600 instead of $8).
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Import validation function from autonomous_trader
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


def test_order_validation():
    """Test order size validation logic."""
    # Import validation function
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "autonomous_trader",
        Path(__file__).parent.parent / "scripts" / "autonomous_trader.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    validate_order_size = module.validate_order_size

    # Test 1: Valid order (within 10% tolerance)
    is_valid, error_msg = validate_order_size(6.0, 6.0, "T1_CORE")
    assert is_valid, "Valid order should pass"
    assert error_msg == "", "Valid order should have no error"

    # Test 2: Order >10x expected (Mistake #1 scenario)
    is_valid, error_msg = validate_order_size(1600.0, 8.0, "T1_CORE")
    assert not is_valid, "Order >10x expected should be rejected"
    assert "10x" in error_msg.lower() or "multiplier" in error_msg.lower(), (
        "Error message should mention multiplier"
    )

    # Test 3: Order too small (<$10 minimum)
    is_valid, error_msg = validate_order_size(5.0, 5.0, "T1_CORE")
    assert not is_valid, "Order <$10 should be rejected"
    assert "minimum" in error_msg.lower(), "Error message should mention minimum"

    # Test 4: Order within 10% variance (should pass)
    is_valid, error_msg = validate_order_size(6.5, 6.0, "T1_CORE")
    assert is_valid, "Order within 10% variance should pass"

    print("✅ All order validation tests passed")


if __name__ == "__main__":
    test_order_validation()
